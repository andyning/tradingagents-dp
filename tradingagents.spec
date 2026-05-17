# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec for TradingAgents — single-file Windows executable.

Build:  python -m PyInstaller tradingagents.spec --clean --noconfirm
Output: dist/TradingAgents.exe
"""

a = Analysis(
    # ── Entry point ──
    ["main_entry.py"],

    pathex=["."],

    # ── Data files: Jinja2 templates + .env template ──
    datas=[
        ("tradingagents/agents/prompts/*.j2", "tradingagents/agents/prompts"),
        (".env.example", "."),
    ],

    # ── Hidden imports: Streamlit internals ──
    hiddenimports=[
        # Streamlit core
        "streamlit",
        "streamlit.web.bootstrap",
        "streamlit.web.server",
        "streamlit.web.server.websocket_headers",
        "streamlit.runtime",
        "streamlit.runtime.scriptrunner",
        "streamlit.runtime.scriptrunner.script_runner",
        "streamlit.runtime.scriptrunner.script_run_context",
        "streamlit.runtime.state",
        "streamlit.runtime.state.session_state",
        "streamlit.runtime.caching",
        "streamlit.runtime.caching.cache_data_api",
        "streamlit.runtime.caching.cache_utils",
        "streamlit.runtime.caching.hashing",
        "streamlit.runtime.media_file_storage",
        "streamlit.runtime.memory_media_file_storage",
        "streamlit.runtime.uploaded_file_manager",
        "streamlit.watcher",
        "streamlit.watcher.local_sources_watcher",
        "streamlit.watcher.path_watcher",
        "streamlit.elements",
        "streamlit.elements.widgets",
        "streamlit.elements.widgets.button",
        "streamlit.elements.arrow",
        "streamlit.elements.arrow_altair",
        "streamlit.elements.pyplot",
        "streamlit.elements.plotly_chart",
        "streamlit.elements.map",
        "streamlit.components",
        "streamlit.components.v1",
        # Tornado
        "tornado",
        "tornado.ioloop",
        "tornado.platform.asyncio",
        "tornado.websocket",
        "tornado.web",
        "tornado.httpserver",
        "tornado.netutil",
        "tornado.process",
        # Altair / Vega
        "altair",
        "altair.vegalite",
        "altair.vegalite.v5",
        "altair.utils",
        "altair.utils.data",
        # Pydeck
        "pydeck",
        "pydeck.bindings",
        "pydeck.data_utils",
        # Plotly
        "plotly",
        "plotly.express",
        "plotly.graph_objs",
        "plotly.io",
        # Rich (Streamlit uses internally)
        "rich",
        "rich.console",
        "rich.text",
        "rich.table",
        "rich.live",
        "rich.progress",
        # Config parsers
        "toml",
        "tomli",
        "tomli._parser",
        "semver",
        "tzlocal",
        "tzlocal.win32",
        # File watchers
        "watchdog",
        "watchdog.observers",
        "watchdog.observers.polling",
        "watchfiles",
        # Click
        "click",
        "blinker",
        "tenacity",
        "cachetools",
        # Pandas / NumPy
        "pandas",
        "pandas.plotting",
        "pandas.plotting._matplotlib",
        "numpy",
        "numpy.core",
        "numpy.core.multiarray",
        "numpy.random",
        "numpy.random._common",
        # Asyncio
        "asyncio",
        "asyncio.windows_events",
        # LangGraph (project dependency)
        "langgraph",
        "langgraph.graph",
        "langgraph.graph.state",
        "langgraph.pregel",
        "langgraph.checkpoint",
        "langgraph.checkpoint.sqlite",
        "langgraph.checkpoint.sqlite.aio",
        # Project modules
        "tradingagents",
        "tradingagents.config",
        "tradingagents.exceptions",
        "tradingagents.logging",
        "tradingagents.llm",
        "tradingagents.llm.client",
        "tradingagents.data",
        "tradingagents.data.a_stock",
        "tradingagents.data.hk_stock",
        "tradingagents.data.us_stock",
        "tradingagents.data.cache",
        "tradingagents.data.loader",
        "tradingagents.data.schema",
        "tradingagents.data.retry",
        "tradingagents.data.sources",
        "tradingagents.data.sources.base",
        "tradingagents.data.sources.akshare",
        "tradingagents.data.sources.baostock",
        "tradingagents.data.sources.efinance",
        "tradingagents.data.sources.futu",
        "tradingagents.data.sources.ib",
        "tradingagents.data.sources.yfinance",
        "tradingagents.agents",
        "tradingagents.agents.base",
        "tradingagents.agents.prompts",
        "tradingagents.graph",
        "tradingagents.graph.builder",
        "tradingagents.graph.graph",
        "tradingagents.graph.nodes",
        "tradingagents.graph.state",
        "tradingagents.graph.progress",
        "tradingagents.graph.signal_processor",
        "tradingagents.graph.memory_store",
        "tradingagents.graph.data_context",
        "tradingagents.graph.routing",
        "tradingagents.graph.reflection",
        "tradingagents.graph.checkpoint",
        "tradingagents.web",
        "tradingagents.web.app",
        "tradingagents.web.api",
        "tradingagents.web.launch",
        "tradingagents.backtesting",
        "tradingagents.backtesting.engine",
        "tradingagents.backtesting.broker",
        "tradingagents.backtesting.metrics",
        "tradingagents.backtesting.reporter",
        "tradingagents.cli",
        "tradingagents.cli.main",
        # Backtrader
        "backtrader",
        "backtrader.feeds",
        "backtrader.indicators",
        # Jinja2
        "jinja2",
        "jinja2.ext",
        # fpdf2
        "fpdf",
        "fpdf.enums",
        "fpdf.html",
        # baostock, efinance, akshare, yfinance
        "baostock",
        "efinance",
        "akshare",
        "yfinance",
        # Requests / HTTP
        "requests",
        "httpx",
        "urllib3",
        "certifi",
        # tqdm
        "tqdm",
        # typing-extensions
        "typing_extensions",
        # pytz
        "pytz",
        # ib_insync (for IB data source)
        "ib_insync",
        "ib_insync.ib",
        "ib_insync.objects",
        "ib_insync.contract",
        "ib_insync.order",
        "ib_insync.util",
        # futu-api
        "futu",
        "futu.quote",
        "futu.quote.open_quote_context",
        "futu.common",
        # pydantic / pydantic-settings
        "pydantic",
        "pydantic_settings",
        # python-dotenv
        "dotenv",
        # structlog
        "structlog",
    ],

    # ── Exclude: unused large packages ──
    exclude_binaries=[],
    excludes=[
        "tkinter",
        "_tkinter",
        "test",
        "unittest",
        "pytest",
        "IPython",
        "jupyter",
        "matplotlib.tests",
        "matplotlib.backends.backend_qt",
        "matplotlib.backends.backend_qt5",
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_gtk3",
        "matplotlib.backends.backend_gtk4",
        "matplotlib.backends.backend_wx",
        "matplotlib.backends.backend_webagg",
        "scipy",
        "scipy.spatial",
        "PIL",
        "Pillow",
        "cv2",
        "torch",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=None,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# Collect all from streamlit, tornado, altair, plotly, pandas, rich
a.datas += [
    *Tree("tradingagents/agents/prompts", prefix="tradingagents/agents/prompts"),
]

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="TradingAgents",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
