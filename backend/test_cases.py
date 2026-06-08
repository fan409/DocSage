"""
DocSage RAG 评估测试集 - 15-20 个问答对，覆盖 Spring、MyBatis、LangChain。

每条包含:
- question: 用户可能提出的问题
- expected_keywords: 答案中应出现的关键词（至少命中一个即视为召回成功）
- source: 对应的文档源
"""

TEST_CASES = [
    # ── Spring Framework ──────────────────────────────────────────────
    {
        "question": "Spring @Transactional 注解的 propagation 属性有哪些可选值？",
        "expected_keywords": ["REQUIRED", "REQUIRES_NEW", "NESTED", "SUPPORTS", "NOT_SUPPORTED", "MANDATORY", "NEVER"],
        "source": "spring",
    },
    {
        "question": "Spring Bean 的生命周期包括哪些阶段？",
        "expected_keywords": ["实例化", "属性注入", "初始化", "init", "destroy", "BeanPostProcessor", "Aware"],
        "source": "spring",
    },
    {
        "question": "Spring AOP 中 Pointcut 和 Advice 的区别是什么？",
        "expected_keywords": ["切入点", "通知", "增强", "连接点", "JoinPoint", "Aspect"],
        "source": "spring",
    },
    {
        "question": "如何在 Spring 中配置 RESTful API 的异常处理？",
        "expected_keywords": ["@ExceptionHandler", "@ControllerAdvice", "ResponseEntity", "ProblemDetail", "ResponseStatus"],
        "source": "spring",
    },
    {
        "question": "Spring 的 @Qualifier 注解有什么作用？",
        "expected_keywords": ["限定符", "多个实现", "Bean注入", "@Autowired", "歧义"],
        "source": "spring",
    },
    # ── MyBatis ───────────────────────────────────────────────────────
    {
        "question": "MyBatis 的一级缓存和二级缓存有什么区别？",
        "expected_keywords": ["SqlSession", "session", "namespace", "默认开启", "生命周期", "flushCache"],
        "source": "mybatis",
    },
    {
        "question": "MyBatis 中 #{} 和 ${} 的区别是什么？",
        "expected_keywords": ["预编译", "PreparedStatement", "占位符", "字符串替换", "SQL注入", "安全"],
        "source": "mybatis",
    },
    {
        "question": "MyBatis 如何配置动态 SQL？有哪些标签？",
        "expected_keywords": ["<if>", "<where>", "<foreach>", "<choose>", "<set>", "<trim>", "动态SQL"],
        "source": "mybatis",
    },
    {
        "question": "MyBatis 的 Mapper 接口是如何绑定 XML 的？",
        "expected_keywords": ["namespace", "接口全限定名", "方法名", "statement id", "动态代理", "MapperProxy"],
        "source": "mybatis",
    },
    {
        "question": "MyBatis 插件（Interceptor）的原理是什么？",
        "expected_keywords": ["Plugin", "Interceptor", "代理", "Executor", "StatementHandler", "ParameterHandler", "ResultSetHandler"],
        "source": "mybatis",
    },
    # ── LangChain ─────────────────────────────────────────────────────
    {
        "question": "LangChain 中如何自定义一个 Tool？",
        "expected_keywords": ["@tool", "BaseTool", "args_schema", "_run", "name", "description"],
        "source": "langchain",
    },
    {
        "question": "LangChain 的 LCEL 是什么？如何用它构建 chain？",
        "expected_keywords": ["LangChain Expression Language", "pipe", "|", "Runnable", "invoke", "chain"],
        "source": "langchain",
    },
    {
        "question": "LangChain 中如何使用 OutputParser 解析 LLM 输出？",
        "expected_keywords": ["OutputParser", "parse", "format_instructions", "StrOutputParser", "JsonOutputParser"],
        "source": "langchain",
    },
    {
        "question": "LangChain Document Loader 怎么加载 PDF 文件？",
        "expected_keywords": ["PyPDFLoader", "Document", "page_content", "metadata", "load"],
        "source": "langchain",
    },
    {
        "question": "LangChain 中如何实现 RAG 检索增强生成？",
        "expected_keywords": ["RetrievalQA", "VectorStore", "retriever", "embeddings", "Retriever", "context"],
        "source": "langchain",
    },
    {
        "question": "LangChain 的 Memory 组件有哪些类型？",
        "expected_keywords": ["ConversationBufferMemory", "ConversationSummaryMemory", "chat_memory", "buffer"],
        "source": "langchain",
    },
    # ── 跨文档/综合型 ────────────────────────────────────────────────
    {
        "question": "Spring 和 MyBatis 整合时如何配置数据源？",
        "expected_keywords": ["DataSource", "SqlSessionFactory", "MapperScannerConfigurer", "application.properties", "连接池"],
        "source": "spring",
    },
    {
        "question": "如何用 LangChain 调用 Spring Boot 提供的 API？",
        "expected_keywords": ["RequestsGetTool", "API", "HTTP", "REST", "request", "endpoint"],
        "source": "langchain",
    },
]
