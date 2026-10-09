"use client"

import { createContext, useContext, useEffect, useState } from "react"

interface HighContrastContextValue {
  highContrast: boolean
  toggle: () => void
}

const HighContrastContext = createContext<HighContrastContextValue>({
  highContrast: false,
  toggle: () => {},
})

export function HighContrastProvider({ children }: { children: React.ReactNode }) {
  const [highContrast, setHighContrast] = useState(false)

  useEffect(() => {
    const stored = localStorage.getItem("high-contrast")
    if (stored === "true") {
      setHighContrast(true)
      document.documentElement.classList.add("high-contrast")
    }
  }, [])

  function toggle() {
    const next = !highContrast
    setHighContrast(next)
    document.documentElement.classList.toggle("high-contrast", next)
    localStorage.setItem("high-contrast", String(next))
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
