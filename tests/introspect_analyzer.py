try:
    from tf_dependency_analyzer.static.static_analyzer import StaticAnalyzer
    print("StaticAnalyzer found.")
    analyzer = StaticAnalyzer(".")
    print("Methods:", [m for m in dir(analyzer) if not m.startswith("_")])
except Exception as e:
    print(f"Error: {e}")
