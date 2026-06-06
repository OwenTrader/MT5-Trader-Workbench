import '@testing-library/jest-dom'

if (typeof window !== 'undefined') {
  class ResizeObserverMock {
    observe() {}
    unobserve() {}
    disconnect() {}
  }

  if (!(window as any).ResizeObserver) {
    ;(window as any).ResizeObserver = ResizeObserverMock
  }

  if (!(globalThis as any).ResizeObserver) {
    ;(globalThis as any).ResizeObserver = ResizeObserverMock
  }

  Object.defineProperty(window, 'matchMedia', {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }),
  })

  if (!window.HTMLElement.prototype.scrollIntoView) {
    window.HTMLElement.prototype.scrollIntoView = () => {}
  }
}
