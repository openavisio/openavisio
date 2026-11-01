"use client"

import { createContext, useContext, useEffect, useSyncExternalStore } from "react"

interface HighContrastContextValue {
  highContrast: boolean
  toggle: () => void
}

const HighContrastContext = createContext<HighContrastContextValue>({
  highContrast: false,
  toggle: () => {},
})

const listeners = new Set<() => void>()
function subscribe(cb: () => void) {
  listeners.add(cb)
  return () => listeners.delete(cb)
}
const read = () => localStorage.getItem("high-contrast") === "true"

export function HighContrastProvider({ children }: { children: React.ReactNode }) {
  const highContrast = useSyncExternalStore(subscribe, read, () => false)
  useEffect(() => {
    document.documentElement.classList.toggle("high-contrast", highContrast)
  }, [highContrast])

  function toggle() {
    const next = !highContrast
    localStorage.setItem("high-contrast", String(next))
    listeners.forEach((cb) => cb())
  }

  return (
    <HighContrastContext.Provider value={{ highContrast, toggle }}>
      {children}
    </HighContrastContext.Provider>
  )
}

export function useHighContrast() {
  return useContext(HighContrastContext)
}
