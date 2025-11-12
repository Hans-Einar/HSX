import * as vscode from "vscode";
import * as path from "path";
import * as os from "os";
import * as fs from "fs";

const DEFAULT_HOST = "127.0.0.1";
const DEFAULT_PORT = 9998;
const DEFAULT_PID = 1;
const DEFAULT_LOG_LEVEL = "INFO";

export interface HSXDebugConfiguration extends vscode.DebugConfiguration {
  pid?: number;
  host?: string;
  port?: number;
  pythonPath?: string;
  logLevel?: string;
  adapterArgs?: (string | number)[];
  env?: Record<string, string>;
  observerMode?: boolean;
  keepaliveInterval?: number;
  sessionHeartbeat?: number;
}

export class HSXConfigurationProvider implements vscode.DebugConfigurationProvider {
  resolveDebugConfiguration(
    _folder: vscode.WorkspaceFolder | undefined,
    config: HSXDebugConfiguration,
  ): HSXDebugConfiguration | null | undefined {
    if (!config.type) {
      config.type = "hsx";
    }
    if (!config.name) {
      config.name = "HSX Launch";
    }
    if (!config.request) {
      config.request = "launch";
    }
    if (!config.host) {
      config.host = DEFAULT_HOST;
    }
    if (typeof config.port !== "number") {
      config.port = DEFAULT_PORT;
    }
    if (config.pid == null) {
      config.pid = DEFAULT_PID;
    }
    if (!Number.isInteger(config.pid)) {
      throw new Error("HSX configuration requires an integer pid value.");
    }
    if (!config.logLevel) {
      config.logLevel = DEFAULT_LOG_LEVEL;
    }
    if (typeof config.observerMode !== "boolean") {
      config.observerMode = false;
    }
    if (config.keepaliveInterval != null) {
      const parsed = Number(config.keepaliveInterval);
      if (Number.isFinite(parsed) && parsed > 0) {
        config.keepaliveInterval = parsed;
      } else {
        delete config.keepaliveInterval;
      }
    }
    if (config.sessionHeartbeat != null) {
      const parsed = Number(config.sessionHeartbeat);
      if (Number.isFinite(parsed) && parsed > 0) {
        config.sessionHeartbeat = parsed;
      } else {
        delete config.sessionHeartbeat;
      }
    }
    return config;
  }
}

export class HSXAdapterFactory implements vscode.DebugAdapterDescriptorFactory, vscode.Disposable {
  private readonly adapterScript: string;

  constructor(private readonly context: vscode.ExtensionContext) {
    this.adapterScript = context.asAbsolutePath(path.join("debugAdapter", "hsx-dap.py"));
  }

  createDebugAdapterDescriptor(session: vscode.DebugSession): vscode.ProviderResult<vscode.DebugAdapterDescriptor> {
    const config = session.configuration as HSXDebugConfiguration;
    const pythonCommand = this.resolvePythonCommand(config);
    const args = this.buildArguments(config);
    const options: vscode.DebugAdapterExecutableOptions = {};
    const mergedEnv = this.mergeEnv(config.env);
    if (mergedEnv) {
      options.env = mergedEnv;
    }
    return new vscode.DebugAdapterExecutable(pythonCommand, args, options);
  }

  dispose(): void {
    // nothing to cleanup; factory registered for lifecycle symmetry
  }

  private resolvePythonCommand(config: HSXDebugConfiguration): string {
    if (config.pythonPath) {
      return config.pythonPath;
    }
    if (process.env.PYTHON) {
      return process.env.PYTHON;
    }
    if (process.env.HSX_PYTHON) {
      return process.env.HSX_PYTHON;
    }
    if (process.env.CONDA_PREFIX) {
      const bin = process.platform === "win32" ? "python.exe" : "bin/python";
      return path.join(process.env.CONDA_PREFIX, bin);
    }
    return process.platform === "win32" ? "python" : "python3";
  }

  private buildArguments(config: HSXDebugConfiguration): string[] {
    const args: string[] = [
      this.adapterScript,
      "--pid",
      String(config.pid ?? DEFAULT_PID),
      "--host",
      String(config.host ?? DEFAULT_HOST),
      "--port",
      String(config.port ?? DEFAULT_PORT),
      "--log-file",
      this.createLogFile(),
      "--log-level",
      String(config.logLevel ?? DEFAULT_LOG_LEVEL).toUpperCase(),
    ];
    if (Array.isArray(config.adapterArgs)) {
      for (const value of config.adapterArgs) {
        args.push(String(value));
      }
    }
    return args;
  }

  private createLogFile(): string {
    const dir = path.join(os.tmpdir(), "hsx-debug");
    try {
      fs.mkdirSync(dir, { recursive: true });
    } catch (error) {
      console.warn(`[hsx-dap] unable to create log directory ${dir}: ${error}`);
    }
    return path.join(dir, `hsx-dap-${Date.now()}.log`);
  }

  private mergeEnv(extra?: Record<string, string>): Record<string, string> | undefined {
    const result: Record<string, string> = {};
    for (const key of Object.keys(process.env)) {
      const value = process.env[key];
      if (typeof value === "string") {
        result[key] = value;
      }
    }
    if (extra) {
      for (const [key, value] of Object.entries(extra)) {
        if (typeof value === "string") {
          result[key] = value;
        }
      }
    }
    return Object.keys(result).length ? result : undefined;
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const provider = new HSXConfigurationProvider();
  context.subscriptions.push(vscode.debug.registerDebugConfigurationProvider("hsx", provider));

  const factory = new HSXAdapterFactory(context);
  context.subscriptions.push(factory);
  context.subscriptions.push(vscode.debug.registerDebugAdapterDescriptorFactory("hsx", factory));

  const trackerFactory = new HSXStatusTrackerFactory();
  context.subscriptions.push(vscode.debug.registerDebugAdapterTrackerFactory("hsx", trackerFactory));
}

export function deactivate(): void {
  // VS Code disposes registered subscriptions for us.
}

class HSXStatusTracker implements vscode.DebugAdapterTracker {
  private disposed = false;

  constructor(private readonly item: vscode.StatusBarItem) {
    this.render("HSX: Starting...", "Waiting for adapter");
  }

  onDidSendMessage(message: vscode.DebugProtocolMessage): void {
    if (message.type !== "event") {
      return;
    }
    const eventMessage = message as vscode.DebugProtocolEvent;
    if (eventMessage.event !== "telemetry") {
      return;
    }
    const body = eventMessage.body ?? {};
    if (body.subsystem !== "hsx-connection") {
      return;
    }
    const state = String(body.state || "").toLowerCase();
    const details = body.details ?? {};
    switch (state) {
      case "connected":
        this.render(`HSX: Connected (${details.pid ?? "pid ?"})`, `Host ${details.host ?? ""}:${details.port ?? ""}`);
        break;
      case "reconnecting":
        this.render("HSX: Reconnecting…", body.message ?? "");
        break;
      case "error":
        this.render("HSX: Error", body.message ?? "connection error");
        vscode.window.showWarningMessage(`HSX debugger connection issue: ${body.message ?? "unknown error"}`);
        break;
      case "disconnected":
        this.render("HSX: Disconnected", undefined, false);
        break;
      default:
        this.render(`HSX: ${state}`, body.message);
    }
  }

  onWillStopSession(): void {
    this.dispose();
  }

  onError(): void {
    this.dispose();
  }

  private render(text: string, tooltip?: string, show: boolean = true): void {
    if (this.disposed) {
      return;
    }
    this.item.text = text;
    this.item.tooltip = tooltip;
    if (show) {
      this.item.show();
    } else {
      this.item.hide();
    }
  }

  private dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.item.hide();
    this.item.dispose();
  }
}

class HSXStatusTrackerFactory implements vscode.DebugAdapterTrackerFactory {
  createDebugAdapterTracker(): vscode.DebugAdapterTracker {
    const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left);
    return new HSXStatusTracker(item);
  }
}
