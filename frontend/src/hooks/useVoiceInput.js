import { useState, useRef, useCallback, useEffect } from 'react'

export function useVoiceInput({ onVoiceEnd } = {}) {
  const [isListening, setIsListening] = useState(false)
  const [transcript, setTranscript] = useState('')
  const [isSupported, setIsSupported] = useState(true)
  const recognitionRef = useRef(null)
  const transcriptRef = useRef('')
  const manualStopRef = useRef(false)
  const onVoiceEndRef = useRef(onVoiceEnd)

  useEffect(() => {
    onVoiceEndRef.current = onVoiceEnd
  }, [onVoiceEnd])

  const startListening = useCallback(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setIsSupported(false)
      return
    }

    if (recognitionRef.current) {
      recognitionRef.current.abort()
    }

    const recognition = new SpeechRecognition()
    recognition.lang = 'zh-CN'
    recognition.interimResults = true
    recognition.continuous = false
    recognition.maxAlternatives = 1

    manualStopRef.current = false
    transcriptRef.current = ''

    recognition.onresult = (event) => {
      let final = ''
      let interim = ''
      for (let i = event.resultIndex; i < event.results.length; i++) {
        if (event.results[i].isFinal) {
          final += event.results[i][0].transcript
        } else {
          interim += event.results[i][0].transcript
        }
      }
      const text = final || interim
      transcriptRef.current = text
      setTranscript(text)
    }

    recognition.onerror = (event) => {
      if (event.error === 'aborted') return
      console.error('Speech recognition error:', event.error)
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        setIsSupported(false)
      }
    }

    recognition.onend = () => {
      setIsListening(false)
      recognitionRef.current = null
      if (!manualStopRef.current && onVoiceEndRef.current) {
        onVoiceEndRef.current(transcriptRef.current)
      }
    }

    recognitionRef.current = recognition
    recognition.start()
    setIsListening(true)
  }, [])

  const stopListening = useCallback(() => {
    manualStopRef.current = true
    if (recognitionRef.current) {
      recognitionRef.current.stop()
      recognitionRef.current = null
    }
    setIsListening(false)
  }, [])

  const clearTranscript = useCallback(() => {
    transcriptRef.current = ''
    setTranscript('')
  }, [])

  return { isListening, transcript, isSupported, startListening, stopListening, clearTranscript }
}
