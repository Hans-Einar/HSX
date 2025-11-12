import * as vscode from "vscode";
import * as path from "path";
import * as os from "os";
import * as fs from "fs";
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

  constructor(private readonly context: vscode.ExtensionContext) {
    this.adapterScript = context.asAbsolutePath(path.join("debugAdapter", "hsx-dap.py"));
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

  const disassemblyProvider = new HSXDisassemblyViewProvider(coordinator);
  const disassemblyView = vscode.window.createTreeView("hsxDisassemblyView", {
    treeDataProvider: disassemblyProvider,
    showCollapseAll: false,
  });
  context.subscriptions.push(disassemblyProvider, disassemblyView);
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
    if (body.subsystem !== "hsx-connection") {
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
        this.render(`HSX: Connected (${pidLabel})`, hostSummary);
        break;
      case "reconnecting":
        this.render("HSX: Reconnecting…", optionalString(body.message));
        break;
      case "error":
        this.render("HSX: Error", optionalString(body.message) ?? "connection error");
        if (typeof body.message === "string") {
          vscode.window.showWarningMessage(`HSX debugger connection issue: ${body.message}`);
        }
        break;
      case "disconnected":
        this.render("HSX: Disconnected", undefined, false);
        break;
      default:
        this.render(`HSX: ${state}`, optionalString(body.message));
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

class HSXDebugViewCoordinator {
  private static singleton: HSXDebugViewCoordinator | undefined;
  private readonly views = new Set<HSXRefreshableView>();
  private readonly frameMetadata = new Map<string, Map<number, FrameMetadata>>();

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
    if (eventName === "stopped" || eventName === "continued" || eventName === "initialized") {
      void this.refreshAll("auto");
    }
    if (eventName === "terminated") {
      this.clearSession(session);
    }
  }

  getFrameMetadata(session: vscode.DebugSession, frameId: number): FrameMetadata | undefined {
    return this.frameMetadata.get(session.id)?.get(frameId);
  }

  clearSession(session: vscode.DebugSession): void {
    this.frameMetadata.delete(session.id);
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

class HSXStackViewProvider implements vscode.TreeDataProvider<vscode.TreeItem>, HSXRefreshableView {
  private readonly emitter = new vscode.EventEmitter<vscode.TreeItem | undefined | void>();
  private rows: vscode.TreeItem[] = [createMessageItem("No stack data")];

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
    }
    this.rows = entries;
  }
}

class HSXDisassemblyViewProvider implements vscode.TreeDataProvider<vscode.TreeItem>, HSXRefreshableView {
  private static readonly WINDOW_BEFORE = 12;
  private static readonly WINDOW_AFTER = 20;
  private static readonly MAX_INSTRUCTION_BYTES = 8;

  private readonly emitter = new vscode.EventEmitter<vscode.TreeItem | undefined | void>();
  private rows: vscode.TreeItem[] = [createMessageItem("No disassembly data")];
  private instructions: DisassembledInstruction[] = [];
  private followPc = true;
  private manualBase: number | undefined;
  private referenceAddress: number | undefined;

  constructor(private readonly coordinator: HSXDebugViewCoordinator) {
    this.coordinator.register(this);
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
    const lines = this.instructions.map((inst) => formatDisassemblyForCopy(inst));
    await vscode.env.clipboard.writeText(lines.join(os.EOL));
    const plural = this.instructions.length === 1 ? "" : "s";
    void vscode.window.showInformationMessage(`Copied ${this.instructions.length} disassembly row${plural} to the clipboard.`);
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
    this.referenceAddress = normalizedCenter;
    const startAddress = this.computeWindowStart(normalizedCenter);
    try {
      const response = await session.customRequest("disassemble", {
        instructionCount: this.instructionWindowSize,
        memoryReference: formatAddress(startAddress),
        resolveSymbols: true,
      });
      const instructions = Array.isArray(response?.instructions)
        ? (response.instructions as DisassembledInstruction[])
        : [];
      if (instructions.length === 0) {
        this.rows = [createMessageItem("No disassembly available for this region.")];
        return;
      }
      this.instructions = instructions;
      this.rows = instructions.map((inst) => createDisassemblyRow(inst, this.referenceAddress));
    } catch (error) {
      this.rows = [createMessageItem(`Disassembly failed: ${getErrorMessage(error)}`)];
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

function createMemoryRow(address: number, data: Uint8Array): vscode.TreeItem {
  const hex = formatHexBytes(data);
  const ascii = formatAscii(data);
  const label = `${formatAddress(address)}  ${hex}`;
  const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
  item.description = ascii;
  item.tooltip = `${formatAddress(address)}\n${hex}\n${ascii}`;
  return item;
}

function createDisassemblyRow(inst: DisassembledInstruction, highlightAddress?: number): vscode.TreeItem {
  const address = inst.address ?? inst.memoryReference ?? "";
  const opcode = formatInstructionBytesDisplay(inst.instructionBytes);
  const instruction = inst.instruction ? inst.instruction.trim() : "";
  const leftParts = [address, opcode, instruction].filter(Boolean);
  const label = leftParts.length ? leftParts.join("  ") : address || "<instruction>";
  const item = new vscode.TreeItem(label, vscode.TreeItemCollapsibleState.None);
  item.contextValue = "hsxDisassemblyInstruction";

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
  if (highlightAddress !== undefined && instAddress !== undefined && instAddress === highlightAddress) {
    item.iconPath = new vscode.ThemeIcon("debug-stackframe");
  }
  return item;
}

function createMessageItem(message: string): vscode.TreeItem {
  const item = new vscode.TreeItem(message, vscode.TreeItemCollapsibleState.None);
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

function formatDisassemblyForCopy(inst: DisassembledInstruction): string {
  const address = inst.address ?? inst.memoryReference ?? "";
  const opcode = formatInstructionBytesDisplay(inst.instructionBytes);
  const instruction = inst.instruction ? inst.instruction.trim() : "";
  const left = [address, opcode, instruction].filter(Boolean).join("  ") || instruction || address || "<instruction>";
  const locationInfo = describeDisassemblyLocation(inst);
  const metaParts: string[] = [];
  if (inst.symbol) {
    metaParts.push(inst.symbol);
  }
  if (locationInfo.label) {
    metaParts.push(locationInfo.label);
  }
  return metaParts.length ? `${left}    ; ${metaParts.join("  ")}` : left;
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

function parseNumericLiteral(raw?: string): number | undefined {
  if (!raw) {
    return undefined;
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

function getErrorMessage(error: unknown): string {
  if (error instanceof Error) {
    return error.message;
  }
  return String(error);
}
