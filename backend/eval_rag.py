"""
DocSage RAG 检索评估脚本 - 对比 Dense-only vs Hybrid vs Hybrid+Rerank。

用法:
    python backend/eval_rag.py

前提:
    - Milvus 已启动且包含文档向量
    - .env 已配置（MILVUS_HOST, EMBEDDING_MODEL 等）
    - BM25 状态文件存在（data/bm25_state.json）
    - 如需评估 Hybrid+Rerank，还需配置 RERANK_* 环境变量
"""

import json
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from .embedding import embedding_service
from .milvus_client import MilvusManager
from .test_cases import TEST_CASES

# rag_utils.retrieve_documents 可选导入（需要 PG+Redis，不一定随时可用）
try:
    from .rag_utils import retrieve_documents
    RAG_UTILS_AVAILABLE = True
except Exception:
    RAG_UTILS_AVAILABLE = False


TOP_K = 5
REPORT_PATH = Path(__file__).resolve().parent.parent / "eval_report.md"


def is_relevant(text: str, keywords: list[str]) -> bool:
    """Check if text contains at least one expected keyword (case-insensitive)."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords)


def dense_only_retrieve(query: str, top_k: int) -> list[dict]:
    """Dense-only retrieval via Milvus."""
    dense_emb = embedding_service.get_embeddings([query])[0]
    return milvus.dense_retrieve(
        dense_embedding=dense_emb,
        top_k=top_k,
        filter_expr="chunk_level == 3",
    )


def hybrid_retrieve(query: str, top_k: int) -> list[dict]:
    """Hybrid (dense + sparse BM25) retrieval via Milvus."""
    dense_emb = embedding_service.get_embeddings([query])[0]
    sparse_emb = embedding_service.get_sparse_embedding(query)
    return milvus.hybrid_retrieve(
        dense_embedding=dense_emb,
        sparse_embedding=sparse_emb,
        top_k=top_k,
    )


def hybrid_rerank_retrieve(query: str, top_k: int) -> list[dict]:
    """Full pipeline: hybrid + rerank + auto-merge via rag_utils."""
    result = retrieve_documents(query, top_k=top_k)
    return result.get("docs", [])


def evaluate_case(question: str, expected_keywords: list[str], docs: list[dict]) -> dict:
    """Evaluate a single retrieval result against expected keywords."""
    hit = False
    keyword_hits = 0
    total_keywords = len(expected_keywords)
    first_relevant_rank = 0

    for i, doc in enumerate(docs):
        text = doc.get("text", "")
        if is_relevant(text, expected_keywords):
            if not hit:
                hit = True
                first_relevant_rank = i + 1  # 1-indexed
            # Count how many keywords this doc covers
            for kw in expected_keywords:
                if kw.lower() in text.lower():
                    keyword_hits += 1

    # Deduplicate keyword hits (a keyword may appear in multiple docs)
    all_text = " ".join(doc.get("text", "") for doc in docs)
    unique_keyword_hits = sum(1 for kw in expected_keywords if kw.lower() in all_text.lower())

    mrr = 1.0 / first_relevant_rank if first_relevant_rank > 0 else 0.0
    keyword_recall = unique_keyword_hits / total_keywords if total_keywords > 0 else 0.0

    return {
        "hit": hit,
        "keyword_recall": keyword_recall,
        "mrr": mrr,
    }


def format_table(results: dict) -> str:
    """Format comparison results as a markdown table."""
    header = "| 模式 | Hit Rate@5 | Avg Keyword Recall | Avg MRR |"
    separator = "|------|-----------|-------------------|---------|"
    rows = []
    for mode, metrics in results.items():
        rows.append(
            f"| {mode} | {metrics['hit_rate']:.2f} | {metrics['keyword_recall']:.2f} | {metrics['mrr']:.2f} |"
        )
    return "\n".join([header, separator] + rows)


def format_terminal_table(results: dict) -> str:
    """Format comparison results as a terminal-friendly table."""
    col_w = 22
    header = f"{'模式':<{col_w}} {'Hit Rate@5':>12} {'Keyword Recall':>15} {'Avg MRR':>10}"
    line = "-" * len(header)
    rows = [header, line]
    for mode, metrics in results.items():
        rows.append(
            f"{mode:<{col_w}} {metrics['hit_rate']:>12.2f} {metrics['keyword_recall']:>15.2f} {metrics['mrr']:>10.2f}"
        )
    return "\n".join(rows)


def run_evaluation():
    """Run evaluation across all modes and test cases."""
    modes = {
        "Dense-only": dense_only_retrieve,
        "Hybrid": hybrid_retrieve,
    }
    if RAG_UTILS_AVAILABLE:
        modes["Hybrid+Rerank"] = hybrid_rerank_retrieve
    else:
        print("[WARN] rag_utils not available (PG/Redis required), skipping Hybrid+Rerank mode\n")

    results = {}
    detailed_results = {}

    for mode_name, retrieve_fn in modes.items():
        print(f"\n{'─'*40}")
        print(f"  Evaluating: {mode_name}")
        print(f"{'─'*40}")

        hits = 0
        total_keyword_recall = 0.0
        total_mrr = 0.0
        case_results = []

        for i, case in enumerate(TEST_CASES):
            question = case["question"]
            expected_keywords = case["expected_keywords"]
            source = case.get("source", "?")

            try:
                docs = retrieve_fn(question, TOP_K)
                metrics = evaluate_case(question, expected_keywords, docs)
            except Exception as e:
                print(f"  [ERROR] Case {i+1} ({source}): {e}")
                metrics = {"hit": False, "keyword_recall": 0.0, "mrr": 0.0}

            hits += int(metrics["hit"])
            total_keyword_recall += metrics["keyword_recall"]
            total_mrr += metrics["mrr"]
            case_results.append({"case_idx": i + 1, "source": source, **metrics})

            status = "HIT" if metrics["hit"] else "MISS"
            print(f"  [{i+1:>2}/{len(TEST_CASES)}] {status}  recall={metrics['keyword_recall']:.2f}  mrr={metrics['mrr']:.2f}  ({source})")

        n = len(TEST_CASES)
        results[mode_name] = {
            "hit_rate": hits / n if n else 0,
            "keyword_recall": total_keyword_recall / n if n else 0,
            "mrr": total_mrr / n if n else 0,
        }
        detailed_results[mode_name] = case_results

    # Output
    terminal_table = format_terminal_table(results)
    md_table = format_table(results)

    print(f"\n{'='*60}")
    print("  Evaluation Results")
    print(f"{'='*60}")
    print(terminal_table)

    # Generate improvement summary
    if "Dense-only" in results and "Hybrid" in results:
        d = results["Dense-only"]
        h = results["Hybrid"]
        hit_improve = (h["hit_rate"] - d["hit_rate"]) * 100
        recall_improve = (h["keyword_recall"] - d["keyword_recall"]) * 100
        mrr_improve = (h["mrr"] - d["mrr"]) * 100
        print(f"\n  Hybrid vs Dense-only: Hit Rate {hit_improve:+.0f}%, "
              f"Keyword Recall {recall_improve:+.0f}%, MRR {mrr_improve:+.0f}%")

    if "Hybrid+Rerank" in results and "Hybrid" in results:
        h = results["Hybrid"]
        hr = results["Hybrid+Rerank"]
        hit_improve = (hr["hit_rate"] - h["hit_rate"]) * 100
        recall_improve = (hr["keyword_recall"] - h["keyword_recall"]) * 100
        mrr_improve = (hr["mrr"] - h["mrr"]) * 100
        print(f"  Hybrid+Rerank vs Hybrid: Hit Rate {hit_improve:+.0f}%, "
              f"Keyword Recall {recall_improve:+.0f}%, MRR {mrr_improve:+.0f}%")

    # Write report
    report_lines = [
        "# DocSage RAG Evaluation Report",
        f"\n**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Test cases:** {len(TEST_CASES)}",
        f"**Top-K:** {TOP_K}",
        "",
        "## Results",
        "",
        md_table,
        "",
        "## Analysis",
        "",
    ]

    if "Dense-only" in results and "Hybrid" in results:
        d = results["Dense-only"]
        h = results["Hybrid"]
        hit_improve = (h["hit_rate"] - d["hit_rate"]) * 100
        recall_improve = (h["keyword_recall"] - d["keyword_recall"]) * 100
        mrr_improve = (h["mrr"] - d["mrr"]) * 100
        report_lines.append(
            f"- **Hybrid vs Dense-only**: Hit Rate {hit_improve:+.0f}%, "
            f"Keyword Recall {recall_improve:+.0f}%, MRR {mrr_improve:+.0f}%"
        )

    if "Hybrid+Rerank" in results and "Hybrid" in results:
        h = results["Hybrid"]
        hr = results["Hybrid+Rerank"]
        hit_improve = (hr["hit_rate"] - h["hit_rate"]) * 100
        recall_improve = (hr["keyword_recall"] - h["keyword_recall"]) * 100
        mrr_improve = (hr["mrr"] - h["mrr"]) * 100
        report_lines.append(
            f"- **Hybrid+Rerank vs Hybrid**: Hit Rate {hit_improve:+.0f}%, "
            f"Keyword Recall {recall_improve:+.0f}%, MRR {mrr_improve:+.0f}%"
        )

    report_lines.extend([
        "",
        "## Per-Case Details",
        "",
    ])

    for mode_name, case_results in detailed_results.items():
        report_lines.append(f"### {mode_name}")
        report_lines.append("")
        report_lines.append("| # | Source | Hit | Keyword Recall | MRR |")
        report_lines.append("|---|--------|-----|---------------|-----|")
        for cr in case_results:
            hit_str = "Y" if cr["hit"] else "N"
            report_lines.append(
                f"| {cr['case_idx']} | {cr['source']} | {hit_str} | {cr['keyword_recall']:.2f} | {cr['mrr']:.2f} |"
            )
        report_lines.append("")

    report_text = "\n".join(report_lines)
    REPORT_PATH.write_text(report_text, encoding="utf-8")
    print(f"\n  Report saved to: {REPORT_PATH}")


if __name__ == "__main__":
    print("Initializing Milvus connection and embedding service...")
    milvus = MilvusManager()
    print("Ready.\n")
    run_evaluation()
