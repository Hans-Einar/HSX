import * as assert from "assert";
import { HSXConfigurationProvider, HSXDebugConfiguration } from "../extension";

const provider = new HSXConfigurationProvider();

function resolve(config: HSXDebugConfiguration): HSXDebugConfiguration {
  const result = provider.resolveDebugConfiguration(undefined, config);
  if (!result) {
    throw new Error("Configuration provider returned undefined");
  }
  return result;
}

(() => {
  const cfg = resolve({});
  assert.strictEqual(cfg.type, "hsx");
  assert.strictEqual(cfg.name, "HSX Launch");
  assert.strictEqual(cfg.host, "127.0.0.1");
  assert.strictEqual(cfg.port, 9998);
  assert.strictEqual(cfg.pid, 1);
})();

(() => {
  const cfg = resolve({
    type: "hsx",
    name: "Custom",
    request: "launch",
    pid: 5,
    host: "10.0.0.5",
    port: 1234,
  });
  assert.strictEqual(cfg.pid, 5);
  assert.strictEqual(cfg.host, "10.0.0.5");
  assert.strictEqual(cfg.port, 1234);
})();

(() => {
  let error: Error | undefined;
  try {
    provider.resolveDebugConfiguration(undefined, { pid: 1.5 } as HSXDebugConfiguration);
  } catch (err) {
    error = err as Error;
  }
  assert.ok(error, "Expected resolveDebugConfiguration to throw on non-integer pid");
})();

console.log("HSX configuration provider tests passed");
