const vscode = require("vscode");
const path = require("path");

class HSXConfigurationProvider {
  resolveDebugConfiguration(folder, config) {
    config.type = config.type || "hsx";
    config.request = config.request || "launch";
    config.name = config.name || "HSX Launch";
    config.host = config.host || "127.0.0.1";
    config.port = config.port || 9998;
    if (config.pid == null) {
      config.pid = 1;
    }
    return config;
  }
}

class HSXAdapterFactory {
  constructor(context) {
    this.context = context;
  }

  createDebugAdapterDescriptor(session) {
    const defaultPython = process.platform === "win32" ? "python" : "python3";
    const pythonCommand = process.env.PYTHON || process.env.HSX_PYTHON || defaultPython;
    const adapterPath = this.context.asAbsolutePath(path.join("debugAdapter", "hsx-dap.py"));
    return new vscode.DebugAdapterExecutable(pythonCommand, [adapterPath]);
  }

  dispose() {}
}

function activate(context) {
  const provider = new HSXConfigurationProvider();
  context.subscriptions.push(vscode.debug.registerDebugConfigurationProvider("hsx", provider));
  const factory = new HSXAdapterFactory(context);
  context.subscriptions.push(factory);
  context.subscriptions.push(vscode.debug.registerDebugAdapterDescriptorFactory("hsx", factory));
}

function deactivate() {}

module.exports = {
  activate,
  deactivate,
};
