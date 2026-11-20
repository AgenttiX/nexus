/** Switches for tests: whether the code believes it runs in the Android app, and the device's storage. */
let native = false

export const deviceStorage = new Map<string, unknown>()

export function setNative(value: boolean) {
  native = value
}

export function isNativeForTests(): boolean {
  return native
}
