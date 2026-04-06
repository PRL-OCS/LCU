from core.plugins.manager import PluginManager
import os

def verify():
    pm = PluginManager()
    
    # 1. First scan
    print("--- First Scan ---")
    pm.discover_plugins()
    initial_plugins = list(pm.registry.keys())
    print(f"Plugins found: {initial_plugins}")
    
    # 2. Add a new file manually (if not already there)
    new_plugin_path = "LCU_Node/Plugins/telescope/hot_reload_test.py"
    if not os.path.exists(new_plugin_path):
        print(f"Error: {new_plugin_path} not found.")
        return

    # 3. Second scan (The Rescan)
    print("\n--- Second Scan (Rescan) ---")
    pm.discover_plugins()
    final_plugins = list(pm.registry.keys())
    print(f"Plugins found: {final_plugins}")
    
    if "hot_reload_test" in final_plugins:
        print("\nSUCCESS: Hot rescan discovered the new plugin!")
    else:
        print("\nFAILURE: Hot rescan did not find the new plugin.")

if __name__ == "__main__":
    verify()
