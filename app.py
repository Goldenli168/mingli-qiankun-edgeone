import sys
sys.path.insert(0, "/opt/mingli-qiankun/cloud-functions/api")
import importlib.util
spec = importlib.util.spec_from_file_location("default", "/opt/mingli-qiankun/cloud-functions/api/[[default]].py")
default_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(default_module)
app = default_module.app

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000)
