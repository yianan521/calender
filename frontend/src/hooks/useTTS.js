import { useRef, useCallback } from 'react'

export function useTTS() {
  const isSupported = typeof window !== 'undefined' && 'speechSynthesis' in window
  const speakingRef = useRef(false)

  const speak = useCallback((text, options = {}) => {
    if (!isSupported) return false
    const {
      lang = 'zh-CN',
      rate = 1.0,
      pitch = 1.0,
      volume = 1.0,
    } = options

    // Cancel any ongoing speech
    window.speechSynthesis.cancel()

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.lang = lang
    utterance.rate = rate
    utterance.pitch = pitch
    utterance.volume = volume

    utterance.onstart = () => { speakingRef.current = true }
    utterance.onend = () => { speakingRef.current = false }
    utterance.onerror = () => { speakingRef.current = false }

    window.speechSynthesis.speak(utterance)
    return true
  }, [isSupported])

  const stop = useCallback(() => {
    if (isSupported) {
      window.speechSynthesis.cancel()
      speakingRef.current = false
    }
  }, [isSupported])

  const isSpeaking = () => speakingRef.current

  return { speak, stop, isSpeaking, isSupported }
}
