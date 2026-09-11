def test_pyinstaller_entrypoint_imports_package():
    import launcher

    assert callable(launcher.main)
