const vscode = require("vscode");
const path = require("path");
const os = require("os");

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
    this.pyCommand = process.env.PYTHON || process.env.HSX_PYTHON || (process.platform === "win32" ? "python" : "python3");
    if (context.globalState) {
      const key = "hsx.pythonCommand";
      this.pyCommand = context.globalState.get(key, this.pyCommand);
      context.globalState.update(key, this.pyCommand);
    }
  }

  createDebugAdapterDescriptor(session) {
    const pythonCommand = this.pyCommand;
    const adapterPath = this.context.asAbsolutePath(path.join("debugAdapter", "hsx-dap.py"));
    const config = session.configuration || {};
    const pid = config.pid ?? 1;
    const host = config.host || "127.0.0.1";
    const port = config.port || 9998;
    const logDir = path.join(os.tmpdir(), "hsx_debug");
    try {
      require("fs").mkdirSync(logDir, { recursive: true });
    } catch (e) {
      console.warn(`[hsx-dap] failed to create log directory ${logDir}: ${e}`);
    }
    const logFile = path.join(logDir, `hsx-dap-${Date.now()}.log`);
    const args = [
      adapterPath,
      "--pid",
      String(pid),
      "--host",
      String(host),
      "--port",
      String(port),
      "--log-file",
      logFile,
      "--log-level",
      "DEBUG",
    ];
    console.info(
      `[hsx-dap] launching adapter: interpreter=${pythonCommand}, script=${adapterPath}, pid=${pid}, host=${host}, port=${port}, log=${logFile}`,
    );
    return new vscode.DebugAdapterExecutable(pythonCommand, args);
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
