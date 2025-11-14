import * as vscode from "vscode";
import * as path from "path";
import * as os from "os";
import * as fs from "fs";
import * as crypto from "crypto";
import { Buffer } from "buffer";

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
    console.log("[hsx-debug] resolveDebugConfiguration", config);
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
  private readonly adapterVersion: string;

  constructor(private readonly context: vscode.ExtensionContext) {
    this.adapterScript = context.asAbsolutePath(path.join("debugAdapter", "hsx-dap.py"));
    const pkg = context.extension.packageJSON as { version?: string } | undefined;
    const baseVersion = typeof pkg?.version === "string" ? pkg.version : "dev";
    const fingerprint = computeExtensionFingerprint(context.extensionPath);
    this.adapterVersion = fingerprint ? `${baseVersion}+${fingerprint}` : baseVersion;
  }

  createDebugAdapterDescriptor(session: vscode.DebugSession): vscode.ProviderResult<vscode.DebugAdapterDescriptor> {
    const config = session.configuration as HSXDebugConfiguration;
    const pythonCommand = this.resolvePythonCommand(config);
    const args = this.buildArguments(config);
    const options: vscode.DebugAdapterExecutableOptions = {};
    const workspaceRoot = session.workspaceFolder?.uri.fsPath;
    if (workspaceRoot) {
      options.cwd = workspaceRoot;
    }
    const mergedEnv = this.mergeEnv(config.env, workspaceRoot);
    if (mergedEnv) {
      options.env = mergedEnv;
    }
    console.log("[hsx-debug] createDebugAdapterDescriptor", { command: pythonCommand, args, options });
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
      "--adapter-version",
      this.adapterVersion,
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

  private mergeEnv(extra?: Record<string, string>, workspaceRoot?: string): Record<string, string> | undefined {
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
    if (workspaceRoot) {
      if (!result.HSX_REPO_ROOT) {
        result.HSX_REPO_ROOT = workspaceRoot;
      }
      if (!result.HSX_WORKSPACE_ROOT) {
        result.HSX_WORKSPACE_ROOT = workspaceRoot;
      }
      const pythonPathEntries: string[] = [
        workspaceRoot,
        path.join(workspaceRoot, "python"),
      ];
      const existingEntries = result.PYTHONPATH ? result.PYTHONPATH.split(path.delimiter) : [];
      const combined = pythonPathEntries.concat(existingEntries).filter((entry): entry is string => Boolean(entry));
      if (combined.length) {
        const deduped = Array.from(new Set(combined));
        result.PYTHONPATH = deduped.join(path.delimiter);
      }
      if (!result.PYTHONUNBUFFERED) {
        result.PYTHONUNBUFFERED = "1";
      }
    }
    result.HSX_EXTENSION_VERSION = this.adapterVersion;
    return Object.keys(result).length ? result : undefined;
  }
}

export function activate(context: vscode.ExtensionContext): void {
  const provider = new HSXConfigurationProvider();
  context.subscriptions.push(vscode.debug.registerDebugConfigurationProvider("hsx", provider));

  const factory = new HSXAdapterFactory(context);
  context.subscriptions.push(factory);
  context.subscriptions.push(vscode.debug.registerDebugAdapterDescriptorFactory("hsx", factory));

  const coordinator = HSXDebugViewCoordinator.instance;
  const trackerFactory = new HSXStatusTrackerFactory(coordinator);
  context.subscriptions.push(vscode.debug.registerDebugAdapterTrackerFactory("hsx", trackerFactory));

  const memoryProvider = new HSXMemoryViewProvider(context, coordinator);
  const memoryView = vscode.window.createTreeView("hsxMemoryView", {
    treeDataProvider: memoryProvider,
    showCollapseAll: false,
  });
  context.subscriptions.push(memoryProvider, memoryView);

  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.refreshMemory", () => {
      void memoryProvider.refresh("manual");
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.setMemoryBase", async () => {
      const current = memoryProvider.baseLabel;
      const input = await vscode.window.showInputBox({
        prompt: "Enter a memory address or expression (e.g. 0x4000, symbol, SP).",
        placeHolder: current,
        value: current,
      });
      if (!input) {
        return;
      }
      const resolved = await resolveAddressExpression(input);
      if (resolved === "session-required") {
        void vscode.window.showWarningMessage("Start an HSX debug session to resolve expressions.");
        return;
      }
      if (typeof resolved !== "number") {
        void vscode.window.showErrorMessage(`Unable to resolve '${input}' to an address.`);
        return;
      }
      memoryProvider.setBaseAddress(resolved);
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.writeMemory", async () => {
      const session = getActiveHSXSession();
      if (!session) {
        void vscode.window.showWarningMessage("Start an HSX debug session to write memory.");
        return;
      }
      const addressInput = await vscode.window.showInputBox({
        prompt: "Enter the memory address to update.",
        placeHolder: memoryProvider.baseLabel,
        value: memoryProvider.baseLabel,
      });
      if (!addressInput) {
        return;
      }
      const resolved = await resolveAddressExpression(addressInput);
      if (resolved === "session-required") {
        void vscode.window.showWarningMessage("Start an HSX debug session to resolve addresses.");
        return;
      }
      if (resolved === "unresolved") {
        void vscode.window.showErrorMessage(`Unable to resolve '${addressInput}' to an address.`);
        return;
      }
      const bytesInput = await vscode.window.showInputBox({
        prompt: "Enter one or more bytes (hex). Example: DE AD BE EF",
        placeHolder: "DE AD BE EF",
      });
      if (!bytesInput) {
        return;
      }
      const bytes = parseByteSequence(bytesInput);
      if (!bytes) {
        void vscode.window.showErrorMessage("Provide between 1 and 16 bytes using hex (e.g. DE AD BE EF).");
        return;
      }
      try {
        await writeTargetMemory(session, resolved, bytes);
        void vscode.window.showInformationMessage(
          `Wrote ${bytes.length} byte${bytes.length === 1 ? "" : "s"} at ${formatAddress(resolved)}.`,
        );
        void memoryProvider.refresh("manual");
      } catch (error) {
        void vscode.window.showErrorMessage(`Unable to write HSX memory: ${getErrorMessage(error)}`);
      }
    }),
  );

  const registersProvider = new HSXRegistersViewProvider(coordinator);
  const registersView = vscode.window.createTreeView("hsxRegistersView", {
    treeDataProvider: registersProvider,
    showCollapseAll: false,
  });
  context.subscriptions.push(registersProvider, registersView);
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.refreshRegisters", () => {
      void registersProvider.refresh("manual");
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.copyRegisters", () => {
      void registersProvider.copyRegisters();
    }),
  );

  const stackProvider = new HSXStackViewProvider(coordinator);
  const stackView = vscode.window.createTreeView("hsxStackView", {
    treeDataProvider: stackProvider,
    showCollapseAll: false,
  });
  context.subscriptions.push(stackProvider, stackView);
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.refreshStack", () => {
      void stackProvider.refresh("manual");
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.copyStack", () => {
      void stackProvider.copyRows();
    }),
  );

  const disassemblyDocumentProvider = new HSXDisassemblyBreakpointDocumentProvider();
  context.subscriptions.push(
    vscode.workspace.registerTextDocumentContentProvider(
      HSXDisassemblyBreakpointDocumentProvider.scheme,
      disassemblyDocumentProvider,
    ),
  );
  let disassemblyProvider: HSXDisassemblyViewProvider;
  let traceProvider: HSXTraceViewProvider | undefined;
  const disassemblyBreakpointManager = new HSXDisassemblyBreakpointManager(
    disassemblyDocumentProvider,
    (change) => {
      if (disassemblyProvider) {
        void disassemblyProvider.handleBreakpointManagerChange(change);
      }
      if (traceProvider) {
        void traceProvider.handleBreakpointManagerChange(change);
      }
    },
  );
  context.subscriptions.push(disassemblyBreakpointManager);
  disassemblyProvider = new HSXDisassemblyViewProvider(coordinator, disassemblyBreakpointManager);
  const disassemblyView = vscode.window.createTreeView<HSXDisassemblyTreeItem>("hsxDisassemblyView", {
    treeDataProvider: disassemblyProvider,
    showCollapseAll: false,
  });
  context.subscriptions.push(
    disassemblyProvider,
    disassemblyView,
    disassemblyView.onDidChangeSelection((event) => {
      disassemblyProvider.handleSelectionChange(event.selection);
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.refreshDisassembly", () => {
      void disassemblyProvider.refresh("manual");
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.setDisassemblyBase", async () => {
      const input = await vscode.window.showInputBox({
        prompt: "Enter the address or expression to disassemble from.",
        placeHolder: "PC",
      });
      if (!input) {
        return;
      }
      const resolved = await resolveAddressExpression(input);
      if (resolved === "session-required") {
        void vscode.window.showWarningMessage("Start an HSX debug session to resolve expressions.");
        return;
      }
      if (typeof resolved !== "number") {
        void vscode.window.showErrorMessage(`Unable to resolve '${input}' to an address.`);
        return;
      }
      disassemblyProvider.setManualBase(resolved);
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.followProgramCounter", () => {
      disassemblyProvider.followProgramCounter();
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.goToProgramCounter", () => {
      void disassemblyProvider.goToProgramCounter();
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.copyDisassembly", () => {
      void disassemblyProvider.copyVisibleInstructions();
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.disassembly.toggleBreakpoint", async (item?: HSXDisassemblyTreeItem) => {
      await disassemblyProvider.toggleBreakpoint(item);
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.disassembly.clearBreakpoints", () => {
      void disassemblyProvider.clearAllBreakpoints();
    }),
  );

  traceProvider = new HSXTraceViewProvider(context, coordinator, disassemblyBreakpointManager);
  const traceView = vscode.window.createTreeView("hsxTraceView", {
    treeDataProvider: traceProvider,
    showCollapseAll: false,
  });
  context.subscriptions.push(traceProvider, traceView);
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.trace.toggle", () => {
      void traceProvider?.toggleTrace();
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.trace.copy", () => {
      void traceProvider?.copyTrace();
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.trace.refresh", () => {
      void traceProvider?.refresh("manual");
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.addDisassemblyBreakpoint", async () => {
      await disassemblyProvider.addBreakpointAtSelection();
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.playPause", async () => {
      await controlPlayPauseButton(coordinator);
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.disassembly.stepInstruction", async () => {
      await stepHSXInstruction("disassemblyView");
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.trace.stepInstruction", async () => {
      await stepHSXInstruction("traceView");
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.stepInstruction", async () => {
      await stepHSXInstruction("commandPalette");
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.breakpoints.clearAll", async () => {
      await clearAllHSXBreakpoints();
    }),
  );
  context.subscriptions.push(
    vscode.commands.registerCommand("hsx.views.stopSession", async () => {
      await stopActiveHSXSession();
    }),
  );

  context.subscriptions.push(
    vscode.debug.onDidChangeActiveDebugSession(() => {
      void coordinator.refreshAll("auto");
    }),
  );
  context.subscriptions.push(
    vscode.debug.onDidStartDebugSession((session) => {
      if (session.type === "hsx") {
        void coordinator.refreshAll("auto");
      }
    }),
  );
  context.subscriptions.push(
    vscode.debug.onDidChangeActiveStackItem((item) => {
      disassemblyProvider.handleStackItemChange(item);
    }),
  );
  context.subscriptions.push(
    vscode.debug.onDidTerminateDebugSession((session) => {
      if (session.type === "hsx") {
        coordinator.clearSession(session);
        void coordinator.refreshAll("auto");
      }
    }),
  );

  void coordinator.refreshAll("auto");
}

export function deactivate(): void {
  // VS Code disposes registered subscriptions for us.
}

interface DebugEventMessage {
  type: "event";
  event: string;
  body?: Record<string, unknown>;
}

class HSXStatusTracker implements vscode.DebugAdapterTracker {
  private disposed = false;
  private lastConnectionRender: { text: string; tooltip?: string; show: boolean } = {
    text: "HSX: Starting...",
    tooltip: "Waiting for adapter",
    show: true,
  };

  constructor(
    private readonly session: vscode.DebugSession,
    private readonly item: vscode.StatusBarItem,
    private readonly coordinator: HSXDebugViewCoordinator,
  ) {
    this.render("HSX: Starting...", "Waiting for adapter");
  }

  onDidSendMessage(message: vscode.DebugProtocolMessage): void {
    this.coordinator.handleAdapterMessage(this.session, message);
    if (!("type" in message) || message.type !== "event") {
      return;
    }
    const eventMessage = message as DebugEventMessage;
    if (eventMessage.event !== "telemetry" || !eventMessage.body) {
      return;
    }
    const body = eventMessage.body ?? {};
    const subsystem = (body as Record<string, unknown>).subsystem;
    if (subsystem === "hsx-step-mode") {
      const stateValue = String((body as Record<string, unknown>).state || "");
      const enabled = stateValue.toLowerCase() === "enabled";
      const pidLabel = optionalString((body as Record<string, unknown>).pid) ?? "pid ?";
      if (enabled) {
        this.render(`HSX: Debugging (${pidLabel})`, "Manual stepping; breakpoints temporarily ignored");
      } else {
        this.render(
          this.lastConnectionRender.text,
          this.lastConnectionRender.tooltip,
          this.lastConnectionRender.show,
        );
      }
      return;
    }
    if (subsystem !== "hsx-connection") {
      return;
    }
    const state = String(body.state || "").toLowerCase();
    const details = isRecord(body.details) ? body.details : {};
    const pidLabel = optionalString(details.pid) ?? "pid ?";
    const hostLabel = optionalString(details.host);
    const portLabel = optionalString(details.port);
    const hostSummary =
      typeof hostLabel === "string" && typeof portLabel === "string"
        ? `Host ${hostLabel}:${portLabel}`
        : undefined;
    switch (state) {
      case "connected":
        this.renderConnection(`HSX: Connected (${pidLabel})`, hostSummary);
        break;
      case "reconnecting":
        this.renderConnection("HSX: Reconnecting…", optionalString(body.message));
        break;
      case "error":
        this.renderConnection("HSX: Error", optionalString(body.message) ?? "connection error");
        if (typeof body.message === "string") {
          vscode.window.showWarningMessage(`HSX debugger connection issue: ${body.message}`);
        }
        break;
      case "disconnected":
        this.renderConnection("HSX: Disconnected", undefined, false);
        break;
      default:
        this.renderConnection(`HSX: ${state}`, optionalString(body.message));
    }
  }

  onWillStopSession(): void {
    this.dispose();
  }

  onError(): void {
    this.dispose();
  }

  private renderConnection(text: string, tooltip?: string, show: boolean = true): void {
    this.lastConnectionRender = { text, tooltip, show };
    this.render(text, tooltip, show);
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
  constructor(private readonly coordinator: HSXDebugViewCoordinator) {}

  createDebugAdapterTracker(session: vscode.DebugSession): vscode.DebugAdapterTracker {
    const item = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left);
    return new HSXStatusTracker(session, item, this.coordinator);
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function optionalString(value: unknown): string | undefined {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number") {
    return String(value);
  }
  return undefined;
}

type RefreshReason = "manual" | "auto";

interface HSXRefreshableView extends vscode.Disposable {
  refresh(reason?: RefreshReason): Promise<void>;
  handleBreakpointEvent?(payload: Record<string, unknown>): void;
  handleSessionInitialized?(session: vscode.DebugSession): void | Promise<void>;
}

interface DisassembledInstruction {
  address?: string;
  instruction?: string;
  instructionBytes?: string;
  symbol?: string;
  location?: {
    path?: string;
    name?: string;
    sourceReference?: number;
  };
  line?: number;
  column?: number;
  instructionPointerReference?: string;
  memoryReference?: string;
}

interface FrameMetadata {
  address?: number;
  order: number;
  name?: string;
}

interface HSXDisassemblyTreeItem extends vscode.TreeItem {
  addressValue?: number;
  instructionData?: DisassembledInstruction;
}

interface StackRowData {
  address: number;
  value: number;
  ascii: string;
  relative: string;
}

interface RegisterRowData {
  name: string;
  value: string;
  rawValue?: number;
}

interface TraceRecordEntry {
  seq: number;
  address: number;
  instruction?: DisassembledInstruction;
  symbol?: string;
  sourcePath?: string;
  sourceLine?: number;
  breakpoint?: boolean;
}

interface HSXDisassemblyBreakpointChange {
  type: "remove" | "toggle";
  addresses: number[];
  enabled?: boolean;
}

type DebugRunState = "running" | "stopped";

class HSXDebugViewCoordinator {
  private static singleton: HSXDebugViewCoordinator | undefined;
  private readonly views = new Set<HSXRefreshableView>();
  private readonly frameMetadata = new Map<string, Map<number, FrameMetadata>>();
  private readonly sessionStates = new Map<string, DebugRunState>();
  private readonly debugState = new Map<string, boolean>();

  static get instance(): HSXDebugViewCoordinator {
    if (!HSXDebugViewCoordinator.singleton) {
      HSXDebugViewCoordinator.singleton = new HSXDebugViewCoordinator();
    }
    return HSXDebugViewCoordinator.singleton;
  }

  register(view: HSXRefreshableView): void {
    this.views.add(view);
  }

  unregister(view: HSXRefreshableView): void {
    this.views.delete(view);
  }

  async refreshAll(reason: RefreshReason): Promise<void> {
    await Promise.all(
      Array.from(this.views).map(async (view) => {
        try {
          await view.refresh(reason);
        } catch (error) {
          console.warn("[hsx-debug] view refresh failed", error);
        }
      }),
    );
  }

  private async refreshNonDisassembly(reason: RefreshReason): Promise<void> {
    await Promise.all(
      Array.from(this.views)
        .filter((view) => !(view instanceof HSXDisassemblyViewProvider))
        .map(async (view) => {
          try {
            await view.refresh(reason);
          } catch (error) {
            console.warn("[hsx-debug] view refresh failed", error);
          }
        }),
    );
  }

  handleAdapterMessage(session: vscode.DebugSession, message: vscode.DebugProtocolMessage): void {
    if (session.type !== "hsx" || !("type" in message)) {
      return;
    }
    if (message.type === "response") {
      const response = message as { command?: string; success?: boolean; body?: unknown };
      if (response.command === "stackTrace" && response.success !== false) {
        this.captureStackMetadata(session, response.body);
      }
      return;
    }
    const eventName = (message as DebugEventMessage).event;
    const eventMessage = message as DebugEventMessage;
    if (eventName === "telemetry") {
      const body = isRecord(eventMessage.body) ? (eventMessage.body as Record<string, unknown>) : undefined;
      const subsystem = optionalString(body?.subsystem);
      if (subsystem === "hsx-disassembly") {
        void this.refreshDisassembly("auto");
        return;
      }
      if (subsystem === "hsx-step-mode") {
        const rawState = optionalString(body?.state) ?? "";
        const enabled = rawState.toLowerCase() === "enabled";
        this.debugState.set(session.id, enabled);
        void vscode.commands.executeCommand("setContext", "hsx.debugStateActive", enabled);
        return;
      }
      return;
    }
    if (eventName === "breakpoint") {
      const body = isRecord(eventMessage.body) ? (eventMessage.body as Record<string, unknown>) : {};
      this.notifyBreakpointEvent(body);
      return;
    }
    if (eventName === "stopped") {
      this.setSessionState(session, "stopped");
      void this.refreshNonDisassembly("auto");
      return;
    }
    if (eventName === "continued") {
      this.setSessionState(session, "running");
      void this.refreshNonDisassembly("auto");
      return;
    }
    if (eventName === "initialized") {
      this.setSessionState(session, "stopped");
      this.notifySessionInitialized(session);
      void this.refreshAll("auto");
      return;
    }
    if (eventName === "terminated") {
      this.clearSession(session);
    }
  }

  private notifyBreakpointEvent(body: Record<string, unknown>): void {
    for (const view of this.views) {
      if (typeof view.handleBreakpointEvent !== "function") {
        continue;
      }
      try {
        view.handleBreakpointEvent(body);
      } catch (error) {
        console.warn("[hsx-debug] breakpoint event propagation failed", error);
      }
    }
  }

  private notifySessionInitialized(session: vscode.DebugSession): void {
    for (const view of this.views) {
      if (typeof view.handleSessionInitialized !== "function") {
        continue;
      }
      try {
        const maybePromise = view.handleSessionInitialized(session);
        if (maybePromise) {
          void Promise.resolve(maybePromise).catch((error) => {
            console.warn("[hsx-debug] session initialization handler failed", error);
          });
        }
      } catch (error) {
        console.warn("[hsx-debug] session initialization handler failed", error);
      }
    }
  }

  getFrameMetadata(session: vscode.DebugSession, frameId: number): FrameMetadata | undefined {
    return this.frameMetadata.get(session.id)?.get(frameId);
  }

  clearSession(session: vscode.DebugSession): void {
    this.frameMetadata.delete(session.id);
    this.sessionStates.delete(session.id);
    this.debugState.delete(session.id);
  }

  private captureStackMetadata(session: vscode.DebugSession, responseBody: unknown): void {
    const body = isRecord(responseBody) ? responseBody : {};
    const framesPayload = (body as { stackFrames?: unknown }).stackFrames;
    const frames = Array.isArray(framesPayload) ? framesPayload : [];
    if (!frames.length) {
      this.frameMetadata.delete(session.id);
      return;
    }
    const perSession = new Map<number, FrameMetadata>();
    frames.forEach((frame: unknown, index: number) => {
      if (!isRecord(frame)) {
        return;
      }
      const rawId = (frame as { id?: unknown }).id;
      const frameId =
        typeof rawId === "number"
          ? rawId
          : typeof rawId === "string"
            ? Number.parseInt(rawId, 10)
            : undefined;
      if (typeof frameId !== "number" || !Number.isFinite(frameId)) {
        return;
      }
      const typedFrame = frame as { instructionPointerReference?: unknown; name?: unknown };
      const pointerRef = typeof typedFrame.instructionPointerReference === "string" ? typedFrame.instructionPointerReference : undefined;
      const address = pointerRef ? parseNumericLiteral(pointerRef) : undefined;
      const name = typeof typedFrame.name === "string" ? typedFrame.name : undefined;
      perSession.set(frameId, { address, order: index, name });
    });
    this.frameMetadata.set(session.id, perSession);
  }

  getSessionState(session?: vscode.DebugSession): DebugRunState | undefined {
    if (!session) {
      return undefined;
    }
    return this.sessionStates.get(session.id);
  }

  private setSessionState(session: vscode.DebugSession, state: DebugRunState): void {
    this.sessionStates.set(session.id, state);
  }

  private async refreshDisassembly(reason: RefreshReason): Promise<void> {
    const targets = Array.from(this.views).filter(
      (view): view is HSXDisassemblyViewProvider => view instanceof HSXDisassemblyViewProvider,
    );
    if (!targets.length) {
      return;
    }
    await Promise.all(
      targets.map(async (view) => {
        try {
          await view.refresh(reason);
        } catch (error) {
          console.warn("[hsx-debug] disassembly refresh failed", error);
        }
      }),
    );
  }
}

class HSXMemoryViewProvider implements vscode.TreeDataProvider<vscode.TreeItem>, HSXRefreshableView {
  private static readonly workspaceKey = "hsx.memory.baseAddress";
  private readonly emitter = new vscode.EventEmitter<vscode.TreeItem | undefined | void>();
  private rows: vscode.TreeItem[] = [createMessageItem("No data loaded")];
  private baseAddress: number;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly coordinator: HSXDebugViewCoordinator,
  ) {
    this.baseAddress = context.workspaceState.get<number>(HSXMemoryViewProvider.workspaceKey, 0) >>> 0;
    this.coordinator.register(this);
  }

  get baseLabel(): string {
    return formatAddress(this.baseAddress);
  }

  setBaseAddress(address: number): void {
    this.baseAddress = address >>> 0;
    void this.context.workspaceState.update(HSXMemoryViewProvider.workspaceKey, this.baseAddress);
    void this.refresh("manual");
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(): vscode.ProviderResult<vscode.TreeItem[]> {
    return this.rows;
  }

  readonly onDidChangeTreeData: vscode.Event<vscode.TreeItem | undefined | void> = this.emitter.event;

  async refresh(_reason: RefreshReason = "manual"): Promise<void> {
    await this.loadRows();
    this.emitter.fire(undefined);
  }

  dispose(): void {
    this.coordinator.unregister(this);
    this.emitter.dispose();
  }

  private async loadRows(): Promise<void> {
    const session = getActiveHSXSession();
    if (!session) {
      this.rows = [createMessageItem("Start an HSX debug session to inspect memory.")];
      return;
    }
    const data = await readTargetMemory(session, this.baseAddress, 128);
    if (!data || data.length === 0) {
      this.rows = [createMessageItem("Memory read failed.")];
      return;
    }
    const items: vscode.TreeItem[] = [];
    for (let offset = 0; offset < data.length; offset += 16) {
      const slice = data.slice(offset, Math.min(offset + 16, data.length));
      items.push(createMemoryRow((this.baseAddress + offset) >>> 0, slice));
    }
    this.rows = items;
  }
}

class HSXRegistersViewProvider implements vscode.TreeDataProvider<vscode.TreeItem>, HSXRefreshableView {
  private readonly emitter = new vscode.EventEmitter<vscode.TreeItem | undefined | void>();
  private rows: vscode.TreeItem[] = [createMessageItem("No register data")];
  private data: RegisterRowData[] = [];

  constructor(private readonly coordinator: HSXDebugViewCoordinator) {
    this.coordinator.register(this);
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(): vscode.ProviderResult<vscode.TreeItem[]> {
    return this.rows;
  }

  readonly onDidChangeTreeData: vscode.Event<vscode.TreeItem | undefined | void> = this.emitter.event;

  async refresh(_reason: RefreshReason = "manual"): Promise<void> {
    await this.loadRows();
    this.emitter.fire(undefined);
  }

  dispose(): void {
    this.coordinator.unregister(this);
    this.emitter.dispose();
  }

  async copyRegisters(): Promise<void> {
    if (!this.data.length) {
      void vscode.window.showInformationMessage("No HSX registers to copy.");
      return;
    }
    const lines = this.data.map((row) => formatRegisterRowForCopy(row));
    await vscode.env.clipboard.writeText(lines.join(os.EOL));
    void vscode.window.showInformationMessage(`Copied ${this.data.length} register${this.data.length === 1 ? "" : "s"} to the clipboard.`);
  }

  private async loadRows(): Promise<void> {
    const session = getActiveHSXSession();
    this.data = [];
    if (!session) {
      this.rows = [createMessageItem("Start an HSX debug session to inspect registers.")];
      return;
    }
    try {
      const response = await session.customRequest("readRegisters", {});
      const registers = Array.isArray(response?.registers) ? (response.registers as RegisterRowData[]) : [];
      if (!registers.length) {
        this.rows = [createMessageItem("No registers reported by HSX adapter.")];
        return;
      }
      this.data = registers.map((entry) => ({
        name: entry.name,
        value: entry.value,
        rawValue: parseNumericLiteral(entry.value ?? ""),
      }));
      const items = this.data.map((entry) => {
        const label = `${entry.name.padEnd(4, " ")} ${entry.value}`;
        return new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
      });
      this.rows = items;
    } catch (error) {
      this.rows = [createMessageItem(`Unable to read registers: ${getErrorMessage(error)}`)];
    }
  }
}

class HSXStackViewProvider implements vscode.TreeDataProvider<vscode.TreeItem>, HSXRefreshableView {
  private readonly emitter = new vscode.EventEmitter<vscode.TreeItem | undefined | void>();
  private rows: vscode.TreeItem[] = [createMessageItem("No stack data")];
  private data: StackRowData[] = [];

  constructor(private readonly coordinator: HSXDebugViewCoordinator) {
    this.coordinator.register(this);
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(): vscode.ProviderResult<vscode.TreeItem[]> {
    return this.rows;
  }

  readonly onDidChangeTreeData: vscode.Event<vscode.TreeItem | undefined | void> = this.emitter.event;

  async refresh(_reason: RefreshReason = "manual"): Promise<void> {
    await this.loadRows();
    this.emitter.fire(undefined);
  }

  async copyRows(): Promise<void> {
    if (!this.data.length) {
      void vscode.window.showInformationMessage("No HSX stack rows to copy.");
      return;
    }
    const lines = this.data.map((row, index) => formatStackRowForCopy(row, index === 0));
    await vscode.env.clipboard.writeText(lines.join(os.EOL));
    void vscode.window.showInformationMessage(`Copied ${this.data.length} stack row${this.data.length === 1 ? "" : "s"} to the clipboard.`);
  }

  dispose(): void {
    this.coordinator.unregister(this);
    this.emitter.dispose();
  }

  private async loadRows(): Promise<void> {
    const session = getActiveHSXSession();
    if (!session) {
      this.rows = [createMessageItem("Stack unavailable (no HSX session).")];
      return;
    }
    const sp = await readRegisterValue("SP");
    if (sp === undefined) {
      this.rows = [createMessageItem("Unable to read stack pointer.")];
      return;
    }
    const data = await readTargetMemory(session, sp, 64);
    if (!data || data.length === 0) {
      this.rows = [createMessageItem("Unable to read stack memory.")];
      return;
    }
    const entries: vscode.TreeItem[] = [];
    const rowData: StackRowData[] = [];
    for (let offset = 0; offset < data.length; offset += 4) {
      const wordBytes = data.slice(offset, Math.min(offset + 4, data.length));
      const addr = (sp + offset) >>> 0;
      const value = bytesToWord(wordBytes);
      const ascii = formatAscii(wordBytes);
      const label = `${formatAddress(addr)}  ${formatWord(value)}`;
      const relative = offset === 0 ? "SP" : `SP+0x${offset.toString(16).toUpperCase().padStart(2, "0")}`;
      const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
      item.description = ascii ? `${ascii}  ${relative}` : relative;
      item.tooltip = `${label}\n${relative}`;
      entries.push(item);
      rowData.push({ address: addr, value, ascii, relative });
    }
    this.rows = entries;
    this.data = rowData;
  }
}

class HSXDisassemblyViewProvider implements vscode.TreeDataProvider<vscode.TreeItem>, HSXRefreshableView {
  private static readonly WINDOW_BEFORE = 12;
  private static readonly WINDOW_AFTER = 20;
  private static readonly MAX_INSTRUCTION_BYTES = 8;
  private static readonly SELECTION_CONTEXT_KEY = "hsxDisassembly.selectionAvailable";

  private readonly emitter = new vscode.EventEmitter<vscode.TreeItem | undefined | void>();
  private rows: HSXDisassemblyTreeItem[] = [createMessageItem("No disassembly data")];
  private instructions: DisassembledInstruction[] = [];
  private followPc = true;
  private manualBase: number | undefined;
  private referenceAddress: number | undefined;
  private instructionBreakpoints: Set<number> = new Set<number>();
  private selectedItem: HSXDisassemblyTreeItem | undefined;
  private readonly breakpointMetadata = new Map<number, DisassembledInstruction | undefined>();

  constructor(
    private readonly coordinator: HSXDebugViewCoordinator,
    private readonly breakpointManager: HSXDisassemblyBreakpointManager,
  ) {
    this.coordinator.register(this);
    this.refreshBreakpointCacheFromVSCode();
    void vscode.commands.executeCommand("setContext", HSXDisassemblyViewProvider.SELECTION_CONTEXT_KEY, false);
  }

  setManualBase(address: number): void {
    this.followPc = false;
    this.manualBase = address >>> 0;
    void this.refresh("manual");
  }

  followProgramCounter(): void {
    this.followPc = true;
    this.manualBase = undefined;
    void this.refresh("manual");
  }

  async goToProgramCounter(): Promise<void> {
    const pc = await readRegisterValue("PC");
    if (pc === undefined) {
      void vscode.window.showWarningMessage("Unable to read PC register.");
      return;
    }
    this.followPc = false;
    this.manualBase = pc >>> 0;
    await this.refresh("manual");
  }

  async copyVisibleInstructions(): Promise<void> {
    if (!this.instructions.length) {
      void vscode.window.showInformationMessage("No HSX disassembly rows to copy.");
      return;
    }
    const lines = this.instructions.map((inst) =>
      formatDisassemblyForCopy(inst, this.referenceAddress, this.instructionBreakpoints),
    );
    await vscode.env.clipboard.writeText(lines.join(os.EOL));
    const plural = this.instructions.length === 1 ? "" : "s";
    void vscode.window.showInformationMessage(`Copied ${this.instructions.length} disassembly row${plural} to the clipboard.`);
  }

  async clearAllBreakpoints(): Promise<void> {
    if (!this.instructionBreakpoints.size) {
      this.breakpointManager.clear();
      return;
    }
    const session = getActiveHSXSession();
    if (!session) {
      this.instructionBreakpoints.clear();
      this.breakpointManager.clear();
      return;
    }
    try {
      await this.sendInstructionBreakpoints(session, new Set<number>());
    } catch (error) {
      void vscode.window.showErrorMessage(`Unable to clear disassembly breakpoints: ${getErrorMessage(error)}`);
    }
  }

  handleStackItemChange(item: vscode.DebugThread | vscode.DebugStackFrame | undefined): void {
    if (!isDebugStackFrame(item) || item.session.type !== "hsx") {
      return;
    }
    const session = getActiveHSXSession();
    if (!session || session.id !== item.session.id) {
      return;
    }
    const metadata = this.coordinator.getFrameMetadata(item.session, item.frameId);
    if (!metadata || metadata.address === undefined) {
      return;
    }
    if (metadata.order === 0 && this.followPc) {
      return;
    }
    this.followPc = false;
    this.manualBase = metadata.address >>> 0;
    void this.refresh("auto");
  }

  async handleSessionInitialized(session: vscode.DebugSession): Promise<void> {
    if (session.type !== "hsx" || !this.instructionBreakpoints.size) {
      return;
    }
    try {
      await this.sendInstructionBreakpoints(session, new Set(this.instructionBreakpoints));
    } catch (error) {
      void vscode.window.showErrorMessage(`Unable to restore disassembly breakpoints: ${getErrorMessage(error)}`);
    }
  }

  async handleBreakpointManagerChange(change: HSXDisassemblyBreakpointChange): Promise<void> {
    if (change.type === "remove") {
      const next = new Set(this.instructionBreakpoints);
      let mutated = false;
      for (const address of change.addresses) {
        mutated = next.delete(address >>> 0) || mutated;
      }
      if (!mutated) {
        return;
      }
      const session = getActiveHSXSession();
      if (session) {
        try {
          await this.sendInstructionBreakpoints(session, next);
        } catch (error) {
          void vscode.window.showErrorMessage(`Unable to update disassembly breakpoints: ${getErrorMessage(error)}`);
        }
      } else {
        this.instructionBreakpoints = next;
        this.syncBreakpointDisplay(undefined);
      }
      return;
    }
    if (change.type === "toggle" && change.addresses.length) {
      const next = new Set(this.instructionBreakpoints);
      const normalized = change.addresses[0] >>> 0;
      if (change.enabled) {
        next.add(normalized);
      } else {
        next.delete(normalized);
      }
      const session = getActiveHSXSession();
      if (session) {
        try {
          await this.sendInstructionBreakpoints(session, next);
        } catch (error) {
          void vscode.window.showErrorMessage(`Unable to update disassembly breakpoints: ${getErrorMessage(error)}`);
        }
      } else {
        this.instructionBreakpoints = next;
        this.syncBreakpointDisplay(undefined);
      }
    }
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(): vscode.ProviderResult<vscode.TreeItem[]> {
    return this.rows;
  }

  readonly onDidChangeTreeData: vscode.Event<vscode.TreeItem | undefined | void> = this.emitter.event;

  async refresh(_reason: RefreshReason = "manual"): Promise<void> {
    await this.loadRows();
    this.emitter.fire(undefined);
  }

  dispose(): void {
    this.coordinator.unregister(this);
    this.emitter.dispose();
    this.selectedItem = undefined;
    void vscode.commands.executeCommand("setContext", HSXDisassemblyViewProvider.SELECTION_CONTEXT_KEY, false);
  }

  private async loadRows(): Promise<void> {
    const session = getActiveHSXSession();
    this.instructions = [];
    if (!session) {
      this.rows = [createMessageItem("Start an HSX debug session to disassemble code.")];
      return;
    }
    let center = this.followPc ? await readRegisterValue("PC") : this.manualBase;
    if (center === undefined) {
      center = await readRegisterValue("PC");
    }
    if (center === undefined) {
      this.rows = [createMessageItem("Unable to determine program counter.")];
      return;
    }
    const normalizedCenter = center >>> 0;
    const instructionCount = Math.max(1, this.instructionWindowSize);
    const requestPayload: Record<string, unknown> = {
      instructionCount,
      resolveSymbols: true,
    };
    if (this.followPc && this.manualBase === undefined) {
      requestPayload.instructionPointerReference = formatAddress(normalizedCenter);
      requestPayload.aroundPc = true;
    } else {
      const startAddress = this.computeWindowStart(normalizedCenter);
      requestPayload.memoryReference = formatAddress(startAddress);
    }
    let highlightAddress = normalizedCenter;
    try {
      const response = await session.customRequest("disassemble", requestPayload);
      const instructions = Array.isArray(response?.instructions)
        ? (response.instructions as DisassembledInstruction[])
        : [];
      if (instructions.length === 0) {
        this.rows = [createMessageItem("No disassembly available for this region.")];
        return;
      }
      const referenceAddress =
        typeof response?.referenceAddress === "string"
          ? parseNumericLiteral(response.referenceAddress)
          : typeof response?.referenceAddress === "number"
            ? response.referenceAddress
            : undefined;
      if (referenceAddress !== undefined) {
        highlightAddress = referenceAddress >>> 0;
      }
      this.referenceAddress = highlightAddress;
      this.instructions = instructions;
      this.rows = instructions.map((inst) => createDisassemblyRow(inst, this.referenceAddress, this.instructionBreakpoints));
      this.updateBreakpointMetadataFromInstructions(instructions);
      this.syncBreakpointDisplay(session);
    } catch (error) {
      this.rows = [createMessageItem(`Disassembly failed: ${getErrorMessage(error)}`)];
    }
  }

  handleSelectionChange(selection: readonly HSXDisassemblyTreeItem[]): void {
    this.selectedItem = selection.length ? selection[0] : undefined;
    const hasAddress = Boolean(this.selectedItem?.addressValue !== undefined);
    void vscode.commands.executeCommand("setContext", HSXDisassemblyViewProvider.SELECTION_CONTEXT_KEY, hasAddress);
  }

  async toggleBreakpoint(item?: HSXDisassemblyTreeItem): Promise<void> {
    if (!item || item.addressValue === undefined) {
      void vscode.window.showInformationMessage("Select an instruction row to toggle a breakpoint.");
      return;
    }
    const session = getActiveHSXSession();
    if (!session) {
      void vscode.window.showWarningMessage("Start an HSX debug session to toggle instruction breakpoints.");
      return;
    }
    const address = item.addressValue >>> 0;
    const next = new Set(this.instructionBreakpoints);
    if (next.has(address)) {
      next.delete(address);
    } else {
      next.add(address);
    }
    try {
      await this.sendInstructionBreakpoints(session, next);
    } catch (error) {
      void vscode.window.showErrorMessage(`Unable to toggle breakpoint: ${getErrorMessage(error)}`);
    }
  }

  async addBreakpointAtSelection(): Promise<void> {
    if (!this.selectedItem || this.selectedItem.addressValue === undefined) {
      void vscode.window.showInformationMessage("Select an instruction row to add a breakpoint.");
      return;
    }
    const session = getActiveHSXSession();
    if (!session) {
      void vscode.window.showWarningMessage("Start an HSX debug session to manage instruction breakpoints.");
      return;
    }
    const address = this.selectedItem.addressValue >>> 0;
    if (this.instructionBreakpoints.has(address)) {
      void vscode.window.showInformationMessage(`Breakpoint already exists at ${formatAddress(address)}.`);
      return;
    }
    const next = new Set(this.instructionBreakpoints);
    next.add(address);
    try {
      await this.sendInstructionBreakpoints(session, next);
    } catch (error) {
      void vscode.window.showErrorMessage(`Unable to add breakpoint: ${getErrorMessage(error)}`);
    }
  }

  handleBreakpointEvent(payload: Record<string, unknown>): void {
    const reason = optionalString(payload.reason)?.toLowerCase();
    const breakpointPayload = isRecord(payload.breakpoint) ? (payload.breakpoint as Record<string, unknown>) : undefined;
    const addressString = optionalString(breakpointPayload?.instructionReference) ?? optionalString(breakpointPayload?.address);
    const address = parseNumericLiteral(addressString);
    if (address === undefined) {
      return;
    }
    const normalized = address >>> 0;
    if (reason === "removed") {
      this.instructionBreakpoints.delete(normalized);
    } else {
      this.instructionBreakpoints.add(normalized);
    }
    this.syncBreakpointDisplay(getActiveHSXSession());
    void this.refresh("auto");
  }

  private refreshBreakpointCacheFromVSCode(): void {
    const next = new Set<number>();
    for (const bp of vscode.debug.breakpoints) {
      const reference = optionalString((bp as { instructionReference?: unknown }).instructionReference);
      const value = parseNumericLiteral(reference);
      if (value !== undefined) {
        next.add(value >>> 0);
      }
    }
    this.instructionBreakpoints = next;
  }

  private async sendInstructionBreakpoints(session: vscode.DebugSession, next: Set<number>): Promise<void> {
    await session.customRequest("setInstructionBreakpoints", {
      breakpoints: Array.from(next).map((value) => ({
        instructionReference: formatAddress(value),
      })),
    });
    this.instructionBreakpoints = next;
    this.syncBreakpointDisplay(session);
    await this.refresh("auto");
  }

  private syncBreakpointDisplay(session?: vscode.DebugSession): void {
    this.breakpointManager.syncBreakpoints(this.instructionBreakpoints, this.breakpointMetadata, session);
  }

  private updateBreakpointMetadataFromInstructions(instructions: DisassembledInstruction[]): void {
    for (const inst of instructions) {
      const address =
        parseNumericLiteral(inst.address ?? inst.memoryReference ?? inst.instructionPointerReference) ?? undefined;
      if (address === undefined) {
        continue;
      }
      this.breakpointMetadata.set(address >>> 0, inst);
    }
  }

  private computeWindowStart(center: number): number {
    const maskedCenter = center >>> 0;
    const bytesBefore = HSXDisassemblyViewProvider.WINDOW_BEFORE * HSXDisassemblyViewProvider.MAX_INSTRUCTION_BYTES;
    const start = maskedCenter - bytesBefore;
    return start >>> 0;
  }

  private get instructionWindowSize(): number {
    return HSXDisassemblyViewProvider.WINDOW_BEFORE + HSXDisassemblyViewProvider.WINDOW_AFTER + 1;
  }
}

class HSXTraceViewProvider implements vscode.TreeDataProvider<vscode.TreeItem>, HSXRefreshableView {
  private static readonly CONTEXT_KEY = "hsxTrace.enabled";
  private readonly emitter = new vscode.EventEmitter<vscode.TreeItem | undefined | void>();
  private rows: vscode.TreeItem[] = [createMessageItem("Trace disabled. Enable tracing to capture instructions.")];
  private entries: TraceRecordEntry[] = [];
  private traceEnabled: boolean;
  private readonly disasmCache = new Map<number, DisassembledInstruction>();
  private readonly traceLimit = 30;

  constructor(
    private readonly context: vscode.ExtensionContext,
    private readonly coordinator: HSXDebugViewCoordinator,
    private readonly breakpointManager: HSXDisassemblyBreakpointManager,
  ) {
    this.traceEnabled = context.workspaceState.get<boolean>("hsx.trace.enabled", false) ?? false;
    void vscode.commands.executeCommand("setContext", HSXTraceViewProvider.CONTEXT_KEY, this.traceEnabled);
    this.coordinator.register(this);
  }

  getTreeItem(element: vscode.TreeItem): vscode.TreeItem {
    return element;
  }

  getChildren(): vscode.ProviderResult<vscode.TreeItem[]> {
    return this.rows;
  }

  readonly onDidChangeTreeData: vscode.Event<vscode.TreeItem | undefined | void> = this.emitter.event;

  async refresh(_reason: RefreshReason = "manual"): Promise<void> {
    await this.loadRows();
    this.emitter.fire(undefined);
  }

  dispose(): void {
    this.coordinator.unregister(this);
    this.emitter.dispose();
  }

  async toggleTrace(): Promise<void> {
    this.traceEnabled = !this.traceEnabled;
    await this.context.workspaceState.update("hsx.trace.enabled", this.traceEnabled);
    void vscode.commands.executeCommand("setContext", HSXTraceViewProvider.CONTEXT_KEY, this.traceEnabled);
    const session = getActiveHSXSession();
    if (session) {
      try {
        await session.customRequest("traceControl", { enabled: this.traceEnabled });
      } catch (error) {
        void vscode.window.showErrorMessage(`Unable to update trace state: ${getErrorMessage(error)}`);
      }
    }
    await this.refresh("manual");
  }

  async copyTrace(): Promise<void> {
    if (!this.entries.length) {
      void vscode.window.showInformationMessage("No HSX trace records to copy.");
      return;
    }
    const highlightAddress = this.entries[this.entries.length - 1]?.address;
    const lines = this.entries.map((entry) => {
      const inst = entry.instruction ?? this.createFallbackInstruction(entry.address);
      return formatDisassemblyForCopy(inst, highlightAddress, this.breakpointManager.getAddresses());
    });
    await vscode.env.clipboard.writeText(lines.join(os.EOL));
    void vscode.window.showInformationMessage(`Copied ${this.entries.length} trace record${this.entries.length === 1 ? "" : "s"} to the clipboard.`);
  }

  async handleBreakpointManagerChange(_change: HSXDisassemblyBreakpointChange): Promise<void> {
    if (this.traceEnabled && this.entries.length) {
      await this.refresh("auto");
    }
  }

  private async loadRows(): Promise<void> {
    if (!this.traceEnabled) {
      this.rows = [createMessageItem("Trace disabled. Use the trace toolbar button to enable capturing instructions.")];
      return;
    }
    const session = getActiveHSXSession();
    if (!session) {
      this.rows = [createMessageItem("Start an HSX debug session to view trace output.")];
      return;
    }
    const state = this.coordinator.getSessionState(session);
    if (state !== "stopped") {
      this.rows =
        this.entries.length > 0
          ? this.createTraceRows(this.entries, this.breakpointManager.getAddresses())
          : [createMessageItem("Trace records update when the target is paused.")];
      return;
    }
    try {
      const response = await session.customRequest("traceRecords", { limit: this.traceLimit });
      const block = isRecord(response?.trace) ? (response.trace as Record<string, unknown>) : isRecord(response) ? (response as Record<string, unknown>) : {};
      const rawRecords = Array.isArray(block.records) ? (block.records as Array<Record<string, unknown>>) : [];
      const records = await this.resolveTraceRecords(session, rawRecords);
      this.entries = records;
      this.rows =
        records.length > 0
          ? this.createTraceRows(records, this.breakpointManager.getAddresses())
          : [createMessageItem("Trace buffer empty.")];
    } catch (error) {
      this.rows = [createMessageItem(`Unable to read trace records: ${getErrorMessage(error)}`)];
    }
  }

  private async resolveTraceRecords(
    session: vscode.DebugSession,
    rawRecords: Array<Record<string, unknown>>,
  ): Promise<TraceRecordEntry[]> {
    const results: TraceRecordEntry[] = [];
    const uniqueAddresses = new Set<number>();
    for (const entry of rawRecords) {
      const address = parseNumericLiteral(entry.pc as string | number | undefined);
      if (address !== undefined) {
        uniqueAddresses.add(address >>> 0);
      }
    }
    for (const address of uniqueAddresses) {
      if (!this.disasmCache.has(address)) {
        await this.populateInstructionCache(session, address);
      }
    }
    for (const entry of rawRecords.slice(-this.traceLimit)) {
      const address = parseNumericLiteral(entry.pc as string | number | undefined);
      if (address === undefined) {
        continue;
      }
      const normalized = address >>> 0;
      const seq =
        typeof entry.seq === "number"
          ? entry.seq
          : typeof entry.seq === "string"
            ? Number.parseInt(entry.seq, 10) || normalized
            : normalized;
      const instruction = this.disasmCache.get(normalized) ?? this.createFallbackInstruction(normalized);
      results.push({
        seq,
        address: normalized,
        instruction,
      });
    }
    return results.slice(-this.traceLimit);
  }

  private async populateInstructionCache(session: vscode.DebugSession, address: number): Promise<void> {
    try {
      const response = await session.customRequest("disassemble", {
        instructionCount: 1,
        memoryReference: formatAddress(address),
        resolveSymbols: true,
      });
      const instructions = Array.isArray(response?.instructions) ? (response.instructions as DisassembledInstruction[]) : [];
      if (instructions.length) {
          this.disasmCache.set(address, instructions[0]);
          return;
      }
    } catch {
      // ignore
    }
    this.disasmCache.set(address, this.createFallbackInstruction(address));
  }

  private createFallbackInstruction(address: number): DisassembledInstruction {
    return {
      address: formatAddress(address),
      instruction: "<trace>",
      instructionBytes: "",
      instructionPointerReference: formatAddress(address),
    };
  }

  private createTraceRows(entries: TraceRecordEntry[], breakpoints: Set<number>): vscode.TreeItem[] {
    const highlight = entries.length ? entries[entries.length - 1].address : undefined;
    return entries.map((entry) => {
      const inst = entry.instruction ?? this.createFallbackInstruction(entry.address);
      const item = createDisassemblyRow(inst, highlight, breakpoints);
      const seqLabel = `#${entry.seq}`;
      if (item.description) {
        item.description = `${seqLabel}  ${item.description}`;
      } else {
        item.description = seqLabel;
      }
      return item;
    });
  }
}

function createMemoryRow(address: number, data: Uint8Array): vscode.TreeItem {
  const hex = formatHexBytes(data);
  const ascii = formatAscii(data);
  const label = `${formatAddress(address)}  ${hex}`;
  const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
  item.description = ascii;
  item.tooltip = `${formatAddress(address)}\n${hex}\n${ascii}`;
  return item;
}

function createDisassemblyRow(
  inst: DisassembledInstruction,
  highlightAddress?: number,
  breakpoints?: Set<number>,
): HSXDisassemblyTreeItem {
  const address = inst.address ?? inst.memoryReference ?? "";
  const opcode = formatInstructionBytesDisplay(inst.instructionBytes);
  const instruction = inst.instruction ? inst.instruction.trim() : "";
  const leftParts = [address, opcode, instruction].filter(Boolean);
  const label = leftParts.length ? leftParts.join("  ") : address || "<instruction>";
  const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None) as HSXDisassemblyTreeItem;

  const locationInfo = describeDisassemblyLocation(inst);
  const descriptionParts: string[] = [];
  if (inst.symbol) {
    descriptionParts.push(inst.symbol);
  }
  if (locationInfo.label) {
    descriptionParts.push(locationInfo.label);
  }
  item.description = descriptionParts.join("  ") || undefined;
  const tooltipLines = [label];
  if (descriptionParts.length) {
    tooltipLines.push(descriptionParts.join("  "));
  }
  if (locationInfo.tooltip && !tooltipLines.includes(locationInfo.tooltip)) {
    tooltipLines.push(locationInfo.tooltip);
  }
  item.tooltip = tooltipLines.join("\n");
  if (locationInfo.uri) {
    const args: Array<vscode.Uri | { selection: vscode.Range }> = [locationInfo.uri];
    if (locationInfo.range) {
      args.push({ selection: locationInfo.range });
    }
    item.command = {
      title: "Open Source Location",
      command: "vscode.open",
      arguments: args,
    };
  }
  const instAddress = parseNumericLiteral(address || inst.instructionPointerReference);
  item.addressValue = instAddress;
  item.instructionData = inst;
  const hasBreakpoint = typeof instAddress === "number" && breakpoints?.has(instAddress >>> 0);
  if (highlightAddress !== undefined && instAddress !== undefined && instAddress === highlightAddress) {
    item.iconPath = new vscode.ThemeIcon("debug-stackframe");
  } else if (hasBreakpoint) {
    item.iconPath = new vscode.ThemeIcon("debug-breakpoint");
  }
  const contextParts = ["hsxDisassemblyInstruction"];
  if (instAddress !== undefined) {
    contextParts.push("address");
  }
  if (hasBreakpoint) {
    contextParts.push("breakpoint");
  }
  item.contextValue = contextParts.join(".");
  return item;
}

interface DisassemblyBreakpointDocument {
  address: number;
  pid?: number;
  symbol?: string;
  sourcePath?: string;
  sourceLine?: number;
}

class HSXDisassemblyBreakpointDocumentProvider implements vscode.TextDocumentContentProvider {
  static readonly scheme = "hsx-disassembly";

  private readonly emitter = new vscode.EventEmitter<vscode.Uri>();
  private readonly documents = new Map<string, DisassemblyBreakpointDocument>();

  readonly onDidChange?: vscode.Event<vscode.Uri> = this.emitter.event;

  provideTextDocumentContent(uri: vscode.Uri): string {
    const key = uri.toString();
    const doc = this.documents.get(key);
    if (!doc) {
      return "HSX Disassembly breakpoint metadata unavailable.";
    }
    const parts = [
      "HSX Disassembly Breakpoint",
      `PC: ${formatAddress(doc.address)}`,
      typeof doc.pid === "number" ? `PID: ${doc.pid}` : undefined,
      doc.symbol ? `Symbol: ${doc.symbol}` : undefined,
      doc.sourcePath ? `Source: ${doc.sourcePath}${doc.sourceLine ? `:${doc.sourceLine}` : ""}` : undefined,
      "",
      "These breakpoints are managed by the HSX disassembly view.",
    ].filter(Boolean);
    return parts.join("\n");
  }

  update(uri: vscode.Uri, doc: DisassemblyBreakpointDocument): void {
    const key = uri.toString();
    this.documents.set(key, doc);
    this.emitter.fire(uri);
  }

  remove(uri: vscode.Uri): void {
    const key = uri.toString();
    if (this.documents.delete(key)) {
      this.emitter.fire(uri);
    }
  }

  clear(): void {
    if (!this.documents.size) {
      return;
    }
    const uris = Array.from(this.documents.keys()).map((value) => vscode.Uri.parse(value));
    this.documents.clear();
    uris.forEach((uri) => this.emitter.fire(uri));
  }

  dispose(): void {
    this.documents.clear();
    this.emitter.dispose();
  }
}

class HSXDisassemblyBreakpointManager implements vscode.Disposable {
  private readonly breakpoints = new Map<number, vscode.SourceBreakpoint>();
  private readonly uriByAddress = new Map<number, vscode.Uri>();
  private readonly metadataByAddress = new Map<number, DisassemblyBreakpointDocument>();
  private readonly enabledState = new Map<number, boolean>();
  private readonly breakpointToAddress = new Map<vscode.Breakpoint, number>();
  private syncing = false;
  private disposed = false;
  private readonly changeSubscription: vscode.Disposable;

  constructor(
    private readonly provider: HSXDisassemblyBreakpointDocumentProvider,
    private readonly onUserChange: (change: HSXDisassemblyBreakpointChange) => void | Promise<void>,
  ) {
    this.changeSubscription = vscode.debug.onDidChangeBreakpoints((event) => {
      void this.handleBreakpointChanges(event);
    });
  }

  dispose(): void {
    if (this.disposed) {
      return;
    }
    this.disposed = true;
    this.changeSubscription.dispose();
    this.clear();
  }

  clear(): void {
    this.syncing = true;
    try {
      if (this.breakpoints.size) {
        vscode.debug.removeBreakpoints(Array.from(this.breakpoints.values()));
      }
      this.breakpoints.clear();
      this.uriByAddress.clear();
      this.metadataByAddress.clear();
      this.enabledState.clear();
      this.breakpointToAddress.clear();
      this.provider.clear();
    } finally {
      this.syncing = false;
    }
  }

  getAddresses(): Set<number> {
    return new Set(this.breakpoints.keys());
  }

  syncBreakpoints(
    addresses: Set<number>,
    instructionMetadata: Map<number, DisassembledInstruction | undefined>,
    session?: vscode.DebugSession,
  ): void {
    if (this.disposed) {
      return;
    }
    const pid = (session?.configuration as HSXDebugConfiguration | undefined)?.pid;
    this.syncing = true;
    try {
      for (const [address, breakpoint] of Array.from(this.breakpoints.entries())) {
        if (!addresses.has(address)) {
          vscode.debug.removeBreakpoints([breakpoint]);
          const uri = this.uriByAddress.get(address);
          if (uri) {
            this.provider.remove(uri);
            this.uriByAddress.delete(address);
          }
          this.breakpoints.delete(address);
          this.metadataByAddress.delete(address);
          this.enabledState.delete(address);
          this.breakpointToAddress.delete(breakpoint);
        }
      }
      for (const address of addresses) {
        const normalized = address >>> 0;
        const metadata = this.createDocumentData(normalized, pid, instructionMetadata.get(normalized));
        const existing = this.breakpoints.get(normalized);
        const previous = this.metadataByAddress.get(normalized);
        const needsUpdate = !existing || !previous || !this.metadataEquals(previous, metadata);
        if (!needsUpdate) {
          continue;
        }
        if (existing) {
          vscode.debug.removeBreakpoints([existing]);
          this.breakpointToAddress.delete(existing);
        }
        const uri = this.createUri(normalized, pid);
        this.provider.update(uri, metadata);
        const position =
          metadata.sourceLine && metadata.sourceLine > 0
            ? new vscode.Position(Math.max(0, metadata.sourceLine - 1), 0)
            : new vscode.Position(0, 0);
        const breakpoint = new vscode.SourceBreakpoint(new vscode.Location(uri, position), true);
        this.breakpoints.set(normalized, breakpoint);
        this.uriByAddress.set(normalized, uri);
        this.metadataByAddress.set(normalized, metadata);
        this.enabledState.set(normalized, true);
        this.breakpointToAddress.set(breakpoint, normalized);
        vscode.debug.addBreakpoints([breakpoint]);
      }
    } finally {
      this.syncing = false;
    }
  }

  private createDocumentData(
    address: number,
    pid: number | undefined,
    inst?: DisassembledInstruction,
  ): DisassemblyBreakpointDocument {
    const locationInfo = inst ? describeDisassemblyLocation(inst) : undefined;
    const sourcePath = inst?.location?.path ?? locationInfo?.tooltip;
    const sourceLine =
      typeof inst?.line === "number"
        ? inst.line
        : typeof (inst?.location as { line?: number } | undefined)?.line === "number"
          ? (inst?.location as { line?: number }).line
          : undefined;
    return {
      address,
      pid,
      symbol: inst?.symbol,
      sourcePath,
      sourceLine,
    };
  }

  private metadataEquals(a: DisassemblyBreakpointDocument, b: DisassemblyBreakpointDocument): boolean {
    return (
      a.address === b.address &&
      a.pid === b.pid &&
      a.symbol === b.symbol &&
      a.sourcePath === b.sourcePath &&
      a.sourceLine === b.sourceLine
    );
  }

  private createUri(address: number, pid?: number): vscode.Uri {
    const pidLabel = pid === undefined ? "pid-unknown" : `pid-${pid}`;
    return vscode.Uri.parse(`${HSXDisassemblyBreakpointDocumentProvider.scheme}:/${pidLabel}/${formatAddress(address)}`);
  }

  private async handleBreakpointChanges(event: vscode.BreakpointsChangeEvent): Promise<void> {
    if (this.syncing || this.disposed) {
      return;
    }
    const removed: number[] = [];
    for (const breakpoint of event.removed) {
      const address = this.breakpointToAddress.get(breakpoint);
      if (address === undefined) {
        continue;
      }
      removed.push(address);
      this.breakpoints.delete(address);
      this.breakpointToAddress.delete(breakpoint);
      const uri = this.uriByAddress.get(address);
      if (uri) {
        this.provider.remove(uri);
        this.uriByAddress.delete(address);
      }
      this.metadataByAddress.delete(address);
      this.enabledState.delete(address);
    }
    for (const change of event.changed) {
      const address = this.breakpointToAddress.get(change);
      if (address === undefined) {
        continue;
      }
      const previous = this.enabledState.get(address) ?? true;
      if (previous === change.enabled) {
        continue;
      }
      this.enabledState.set(address, change.enabled);
      await this.onUserChange({
        type: "toggle",
        addresses: [address],
        enabled: change.enabled,
      });
    }
    if (removed.length) {
      await this.onUserChange({ type: "remove", addresses: removed });
    }
  }
}

function createMessageItem(message: string): HSXDisassemblyTreeItem {
  const item = new vscode.TreeItem(message, vscode.TreeItemCollapsibleState.None) as HSXDisassemblyTreeItem;
  item.iconPath = new vscode.ThemeIcon("info");
  item.contextValue = "hsxViewMessage";
  return item;
}

interface DisassemblyLocationInfo {
  label?: string;
  tooltip?: string;
  uri?: vscode.Uri;
  range?: vscode.Range;
}

function formatInstructionBytesDisplay(raw?: string): string {
  if (!raw) {
    return "";
  }
  const sanitized = raw.replace(/\s+/g, "").toUpperCase();
  const pairs = sanitized.match(/.{1,2}/g);
  return pairs ? pairs.join(" ") : sanitized;
}

function describeDisassemblyLocation(inst: DisassembledInstruction): DisassemblyLocationInfo {
  const sourcePath = inst.location?.path;
  const sourceName = inst.location?.name;
  const locationSource = inst.location as { line?: number; column?: number } | undefined;
  const locationLine =
    typeof inst.line === "number"
      ? inst.line
      : typeof locationSource?.line === "number"
        ? locationSource.line
        : undefined;
  const locationColumn =
    typeof inst.column === "number"
      ? inst.column
      : typeof locationSource?.column === "number"
        ? locationSource.column
        : undefined;
  if (!sourcePath && !sourceName) {
    return {};
  }
  const labelBase = sourcePath ? path.basename(sourcePath) : sourceName ?? "";
  const label = locationLine ? `${labelBase}:${locationLine}` : labelBase;
  const uri = sourcePath ? vscode.Uri.file(sourcePath) : undefined;
  let range: vscode.Range | undefined;
  if (uri && locationLine) {
    const zeroLine = Math.max(0, locationLine - 1);
    const zeroColumn = locationColumn ? Math.max(0, locationColumn - 1) : 0;
    range = new vscode.Range(zeroLine, zeroColumn, zeroLine, zeroColumn);
  }
  return {
    label: label || undefined,
    tooltip: sourcePath ?? sourceName,
    uri,
    range,
  };
}

function formatDisassemblyForCopy(
  inst: DisassembledInstruction,
  referenceAddress?: number,
  breakpoints?: Set<number>,
): string {
  const address = inst.address ?? inst.memoryReference ?? "";
  const opcode = formatInstructionBytesDisplay(inst.instructionBytes);
  const instruction = inst.instruction ? inst.instruction.trim() : "";
  const normalizedAddress = parseNumericLiteral(
    typeof address === "string" ? address : typeof inst.instructionPointerReference === "string" ? inst.instructionPointerReference : undefined,
  );
  const isReference =
    referenceAddress !== undefined && normalizedAddress !== undefined && normalizedAddress === (referenceAddress >>> 0);
  const hasBreakpoint =
    normalizedAddress !== undefined && breakpoints?.has(normalizedAddress >>> 0) ? true : false;
  const marker = hasBreakpoint ? "0" : " ";
  const margin = isReference ? "|-> " : "|   ";
  const core = [address, opcode, instruction].filter(Boolean).join("  ") || instruction || address || "<instruction>";
  const decoratedLeft = `${marker} ${margin}${core}`;
  const locationInfo = describeDisassemblyLocation(inst);
  const metaParts: string[] = [];
  if (inst.symbol) {
    metaParts.push(inst.symbol);
  }
  if (locationInfo.label) {
    metaParts.push(locationInfo.label);
  }
  return metaParts.length ? `${decoratedLeft}    ; ${metaParts.join("  ")}` : decoratedLeft;
}

function formatStackRowForCopy(row: StackRowData, isTop: boolean): string {
  const marker = " ";
  const margin = isTop ? "|-> " : "|   ";
  const asciiPart = row.ascii ? `  ${row.ascii}` : "";
  const left = `${formatAddress(row.address)}  ${formatWord(row.value)}${asciiPart}`;
  return `${marker} ${margin}${left}    ; ${row.relative}`;
}

function formatRegisterRowForCopy(row: RegisterRowData): string {
  const marker = " ";
  const margin = "|   ";
  const label = `${row.name.padEnd(4, " ")} ${row.value}`;
  return `${marker} ${margin}${label}`;
}

async function readTargetMemory(session: vscode.DebugSession, address: number, length: number): Promise<Uint8Array | undefined> {
  try {
    const response = await session.customRequest("readMemory", {
      memoryReference: formatAddress(address),
      offset: 0,
      count: length,
    });
    const data = response?.data;
    if (typeof data === "string" && data.length > 0) {
      const buffer = Buffer.from(data, "base64");
      return new Uint8Array(buffer);
    }
  } catch (error) {
    console.warn("[hsx-debug] readMemory failed", error);
  }
  return undefined;
}

async function writeTargetMemory(session: vscode.DebugSession, address: number, data: Uint8Array): Promise<void> {
  await session.customRequest("writeMemory", {
    memoryReference: formatAddress(address),
    offset: 0,
    data: Buffer.from(data).toString("base64"),
  });
}

async function readRegisterValue(register: string): Promise<number | undefined> {
  const session = getActiveHSXSession();
  if (!session) {
    return undefined;
  }
  try {
    const response = await session.customRequest("evaluate", { expression: register, context: "watch" });
    const result = typeof response?.result === "string" ? response.result : undefined;
    return parseNumericLiteral(result);
  } catch (error) {
    console.warn("[hsx-debug] evaluate failed", error);
    return undefined;
  }
}

function formatAddress(value: number): string {
  const masked = value >>> 0;
  return `0x${masked.toString(16).toUpperCase().padStart(8, "0")}`;
}

function formatWord(value: number): string {
  const masked = value >>> 0;
  return `0x${masked.toString(16).toUpperCase().padStart(8, "0")}`;
}

function formatHexBytes(data: Uint8Array): string {
  return Array.from(data)
    .map((byte) => byte.toString(16).toUpperCase().padStart(2, "0"))
    .join(" ");
}

function formatAscii(data: Uint8Array): string {
  return Array.from(data)
    .map((byte) => {
      if (byte >= 0x20 && byte <= 0x7e) {
        return String.fromCharCode(byte);
      }
      return ".";
    })
    .join("");
}

function bytesToWord(bytes: Uint8Array): number {
  const padded = new Uint8Array(4);
  padded.set(bytes.slice(0, 4));
  return (padded[0] | (padded[1] << 8) | (padded[2] << 16) | (padded[3] << 24)) >>> 0;
}

function isDebugStackFrame(
  item: vscode.DebugThread | vscode.DebugStackFrame | undefined,
): item is vscode.DebugStackFrame {
  const candidate = item as vscode.DebugStackFrame | undefined;
  return Boolean(candidate && typeof candidate.frameId === "number");
}

function getActiveHSXSession(): vscode.DebugSession | undefined {
  const session = vscode.debug.activeDebugSession;
  if (session && session.type === "hsx") {
    return session;
  }
  return undefined;
}

async function controlPlayPauseButton(coordinator: HSXDebugViewCoordinator): Promise<void> {
  const session = getActiveHSXSession();
  if (!session) {
    void vscode.window.showWarningMessage("Start an HSX debug session to control execution.");
    return;
  }
  const state = coordinator.getSessionState(session);
  const shouldPause = state === "running";
  const commandId = shouldPause ? "workbench.action.debug.pause" : "workbench.action.debug.continue";
  const actionLabel = shouldPause ? "pause" : "continue";
  try {
    await vscode.commands.executeCommand(commandId);
  } catch (error) {
    void vscode.window.showErrorMessage(`Unable to ${actionLabel} HSX target: ${getErrorMessage(error)}`);
  }
}

async function stopActiveHSXSession(): Promise<void> {
  const session = getActiveHSXSession();
  if (!session) {
    void vscode.window.showWarningMessage("Start an HSX debug session to stop the target.");
    return;
  }
  try {
    await session.customRequest("terminate", { restart: false });
  } catch (error) {
    void vscode.window.showErrorMessage(`Unable to stop HSX target: ${getErrorMessage(error)}`);
  }
  }

let singleStepInFlight = false;

async function stepHSXInstruction(origin?: string): Promise<void> {
  const session = getActiveHSXSession();
  if (!session) {
    void vscode.window.showWarningMessage("Start an HSX debug session to step instructions.");
    return;
  }
  if (singleStepInFlight) {
    void vscode.window.showInformationMessage("Single-step already in progress.");
    return;
  }
  singleStepInFlight = true;
  try {
    const payload = origin ? { origin } : {};
    await session.customRequest("stepInstruction", payload);
    await HSXDebugViewCoordinator.instance.refreshAll("auto");
  } catch (error) {
    void vscode.window.showErrorMessage(`Unable to step HSX instruction: ${getErrorMessage(error)}`);
  } finally {
    singleStepInFlight = false;
  }
}

async function clearAllHSXBreakpoints(): Promise<void> {
  const targets = vscode.debug.breakpoints;
  if (targets.length) {
    try {
      vscode.debug.removeBreakpoints(targets);
    } catch (error) {
      void vscode.window.showErrorMessage(`Unable to remove VS Code breakpoints: ${getErrorMessage(error)}`);
    }
  }
  const session = getActiveHSXSession();
  if (!session) {
    void vscode.window.showInformationMessage("Cleared VS Code breakpoints.");
    return;
  }
  try {
    const response = await session.customRequest("clearAllBreakpoints", {});
    const cleared = typeof response?.cleared === "number" ? response.cleared : 0;
    const plural = cleared === 1 ? "" : "s";
    void vscode.window.showInformationMessage(`Cleared ${cleared} breakpoint${plural} from the HSX executive.`);
  } catch (error) {
    void vscode.window.showErrorMessage(`Unable to clear HSX breakpoints: ${getErrorMessage(error)}`);
  }
}

type ResolveResult = number | "session-required" | "unresolved";

async function resolveAddressExpression(input: string): Promise<ResolveResult> {
  const literal = parseNumericLiteral(input);
  if (literal !== undefined) {
    return literal;
  }
  const session = getActiveHSXSession();
  if (!session) {
    return "session-required";
  }
  try {
    const response = await session.customRequest("evaluate", { expression: input, context: "watch" });
    const result = typeof response?.result === "string" ? response.result : undefined;
    const value = parseNumericLiteral(result);
    return value ?? "unresolved";
  } catch (error) {
    console.warn("[hsx-debug] resolve expression failed", error);
    return "unresolved";
  }
}

function parseNumericLiteral(raw?: string | number): number | undefined {
  if (!raw) {
    return undefined;
  }
  if (typeof raw === "number") {
    return raw >>> 0;
  }
  const text = raw.trim();
  if (!text) {
    return undefined;
  }
  const sanitized = text.replace(/_/g, "");
  let base = 10;
  let body = sanitized;
  if (/^0x/i.test(sanitized)) {
    base = 16;
    body = sanitized.slice(2);
  } else if (/^0b/i.test(sanitized)) {
    base = 2;
    body = sanitized.slice(2);
  } else if (/^0o/i.test(sanitized)) {
    base = 8;
    body = sanitized.slice(2);
  } else if (!/^[+-]?\d+$/.test(sanitized)) {
    return undefined;
  }
  const value = parseInt(body, base);
  if (Number.isNaN(value)) {
    return undefined;
  }
  return value >>> 0;
}

function parseByteSequence(input: string): Uint8Array | undefined {
  const sanitized = input.replace(/[,]/g, " ").trim();
  if (!sanitized) {
    return undefined;
  }
  const tokens = sanitized.split(/\s+/);
  if (!tokens.length || tokens.length > 16) {
    return undefined;
  }
  const values: number[] = [];
  for (const token of tokens) {
    let slice = token.trim();
    if (!slice) {
      continue;
    }
    if (/^0x/i.test(slice)) {
      slice = slice.slice(2);
    }
    if (slice.length === 1) {
      slice = `0${slice}`;
    }
    if (!/^[0-9a-fA-F]{2}$/.test(slice)) {
      return undefined;
    }
    const parsed = Number.parseInt(slice, 16);
    if (Number.isNaN(parsed)) {
      return undefined;
    }
    values.push(parsed & 0xff);
  }
  if (!values.length) {
    return undefined;
  }
  return new Uint8Array(values);
}

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}

function computeExtensionFingerprint(extensionPath: string): string | undefined {
  try {
    const packageData = fs.readFileSync(path.join(extensionPath, "package.json"));
    const bundlePath = path.join(extensionPath, "dist", "extension.js");
    const bundleData = fs.readFileSync(bundlePath);
    const hash = crypto.createHash("sha1");
    hash.update(packageData);
    hash.update(bundleData);
    return hash.digest("hex").slice(0, 8);
  } catch (error) {
    console.warn("[hsx-debug] Unable to compute build fingerprint", error);
    return undefined;
  }
}
