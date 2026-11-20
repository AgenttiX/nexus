import { Capacitor } from '@capacitor/core'

/** Whether the interface runs inside the Android app rather than in a browser. */
export function isNative(): boolean {
  return Capacitor.isNativePlatform()
}
