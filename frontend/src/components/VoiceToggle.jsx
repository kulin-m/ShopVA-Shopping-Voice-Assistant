import React, { useState, useEffect, useRef } from 'react';
import { Mic, MicOff, Volume2, VolumeX, Loader2, Sparkles, AlertCircle } from 'lucide-react';
import { api } from '../services/api';

export const VoiceToggle = ({ onCommandProcessed, voiceState, setVoiceState, lastTranscript, setLastTranscript }) => {
  const [isVoiceOn, setIsVoiceOn] = useState(false);
  const [isTtsEnabled, setIsTtsEnabled] = useState(true);
  const [errorMessage, setErrorMessage] = useState('');

  // ── Authoritative Refs for Synchronous Lifecycle Control ─────────────────
  const voiceEnabledRef = useRef(false);
  const ttsEnabledRef = useRef(true);
  const isSpeakingRef = useRef(false);
  const isProcessingRef = useRef(false);
  const shouldRestartRef = useRef(false);
  const isRecognitionActiveRef = useRef(false);
  const sessionVersionRef = useRef(0);
  const recognitionRef = useRef(null);

  // Keep refs in sync with state & handle immediate TTS cancellation
  useEffect(() => {
    voiceEnabledRef.current = isVoiceOn;
  }, [isVoiceOn]);

  useEffect(() => {
    ttsEnabledRef.current = isTtsEnabled;
    console.log(`[ASSISTANT VOICE] ${isTtsEnabled ? 'ON' : 'OFF'}`);

    if (!isTtsEnabled) {
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
        console.log('[TTS] cancelled active & queued speech (assistant voice disabled)');
      }
      isSpeakingRef.current = false;
      if (voiceState === 'SPEAKING') {
        setVoiceState(voiceEnabledRef.current ? 'LISTENING' : 'OFF');
      }
    }
  }, [isTtsEnabled]);

  // ── Recognition Startup / Shutdown Helpers ───────────────────────────────
  const stopRecognitionSafely = () => {
    shouldRestartRef.current = false;
    if (recognitionRef.current && isRecognitionActiveRef.current) {
      try {
        recognitionRef.current.stop();
        console.log('[VOICE] recognition stopped');
      } catch (err) {
        console.warn('[VOICE] stop error:', err);
      }
    }
    isRecognitionActiveRef.current = false;
  };

  const startRecognitionSafely = () => {
    if (!voiceEnabledRef.current) {
      console.log('[VOICE] restart prevented: voice disabled');
      return;
    }
    if (isSpeakingRef.current) {
      console.log('[VOICE] restart prevented: TTS active');
      return;
    }
    if (isProcessingRef.current) {
      console.log('[VOICE] restart prevented: command processing active');
      return;
    }
    if (isRecognitionActiveRef.current) {
      console.log('[VOICE] restart prevented: recognition already active');
      return;
    }
    if (!recognitionRef.current) return;

    try {
      shouldRestartRef.current = true;
      isRecognitionActiveRef.current = true;
      recognitionRef.current.start();
      setVoiceState('LISTENING');
      console.log('[VOICE] recognition started');
    } catch (err) {
      console.warn('[VOICE] start error:', err);
      if (err.name === 'InvalidStateError') {
        isRecognitionActiveRef.current = true;
      } else {
        isRecognitionActiveRef.current = false;
      }
    }
  };

  const turnVoiceOff = () => {
    sessionVersionRef.current += 1; // Invalidate all pending async callbacks
    voiceEnabledRef.current = false;
    setIsVoiceOn(false);

    shouldRestartRef.current = false;
    isProcessingRef.current = false;
    isSpeakingRef.current = false;

    // 1. Cancel any active TTS speech immediately
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    // 2. Stop recognition instance
    stopRecognitionSafely();

    // 3. Set authoritative state to OFF
    setVoiceState('OFF');
    console.log('[VOICE] disabled');
  };

  const turnVoiceOn = () => {
    sessionVersionRef.current += 1;
    voiceEnabledRef.current = true;
    setIsVoiceOn(true);
    shouldRestartRef.current = true;
    setErrorMessage('');
    console.log('[VOICE] enabled');

    startRecognitionSafely();
  };

  // ── TTS Execution with Absolute Microphone Separation ────────────────────
  const speakResponseWithTts = (message, currentSessionId, onTtsDone) => {
    // Check authoritative ttsEnabledRef.current to prevent stale React closure bugs
    if (!ttsEnabledRef.current || !window.speechSynthesis || !message) {
      console.log('[TTS] blocked — assistant voice disabled');
      onTtsDone();
      return;
    }

    // 1. Stop SpeechRecognition immediately BEFORE starting TTS audio
    stopRecognitionSafely();
    isSpeakingRef.current = true;
    setVoiceState('SPEAKING');
    console.log('[TTS] started:', message);

    const finishTts = () => {
      isSpeakingRef.current = false;
      console.log('[TTS] completed');

      if (currentSessionId === sessionVersionRef.current && voiceEnabledRef.current) {
        onTtsDone();
      } else {
        console.log('[VOICE] restart prevented after TTS: voice disabled or session changed');
      }
    };

    try {
      window.speechSynthesis.cancel();
      
      // Re-verify immediately before speak call
      if (!ttsEnabledRef.current) {
        console.log('[TTS] cancelled right before speak — assistant voice disabled');
        finishTts();
        return;
      }

      const utterance = new SpeechSynthesisUtterance(message);
      utterance.onend = () => {
        if (!ttsEnabledRef.current) {
          console.log('[TTS] onend ignored — assistant voice disabled');
          return;
        }
        finishTts();
      };
      utterance.onerror = (e) => {
        console.warn('[TTS] error:', e);
        finishTts();
      };
      window.speechSynthesis.speak(utterance);
    } catch (e) {
      console.warn('[TTS] execution exception:', e);
      finishTts();
    }
  };

  // ── SpeechRecognition Setup Hook ──────────────────────────────────────────
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

    if (!SpeechRecognition) {
      setErrorMessage('Browser does not support Web Speech API. Use Chrome, Edge, or Safari.');
      setVoiceState('ERROR');
      return;
    }

    const recognition = new SpeechRecognition();
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      isRecognitionActiveRef.current = true;
      if (voiceEnabledRef.current && !isSpeakingRef.current && !isProcessingRef.current) {
        setVoiceState('LISTENING');
        setErrorMessage('');
      }
    };

    recognition.onresult = async (event) => {
      const currentSessionId = sessionVersionRef.current;

      let finalTranscript = '';
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const transcriptSegment = event.results[i][0].transcript;
        if (event.results[i].isFinal) {
          finalTranscript += transcriptSegment;
        } else if (voiceEnabledRef.current && !isSpeakingRef.current) {
          setLastTranscript(transcriptSegment);
        }
      }

      if (finalTranscript.trim()) {
        const cleanTranscript = finalTranscript.trim();
        console.log('[VOICE] speech detected:', cleanTranscript);

        // 1. Immediately STOP recognition so microphone doesn't record TTS or ambient noise during processing
        stopRecognitionSafely();
        isProcessingRef.current = true;
        setLastTranscript(cleanTranscript);
        setVoiceState('PROCESSING');
        console.log('[VOICE] processing command');

        try {
          const response = await api.sendVoiceCommand(cleanTranscript);

          // Check if session remains valid
          if (currentSessionId !== sessionVersionRef.current || !voiceEnabledRef.current) {
            console.log('[VOICE] command response ignored: session changed or voice disabled');
            isProcessingRef.current = false;
            return;
          }

          isProcessingRef.current = false;

          // 2. Play TTS feedback (if Assistant Voice is ON) and resume listening
          speakResponseWithTts(response.message, currentSessionId, () => {
            onCommandProcessed(response);
            if (voiceEnabledRef.current && currentSessionId === sessionVersionRef.current) {
              console.log('[VOICE] restarting recognition after command processing & TTS');
              startRecognitionSafely();
            }
          });
        } catch (err) {
          isProcessingRef.current = false;
          if (currentSessionId !== sessionVersionRef.current || !voiceEnabledRef.current) return;

          console.error('[VOICE] Error processing command:', err);
          setErrorMessage(err.response?.data?.detail || 'Failed to process voice command');
          setVoiceState('ERROR');

          // Controlled retry after error
          setTimeout(() => {
            if (voiceEnabledRef.current && currentSessionId === sessionVersionRef.current) {
              startRecognitionSafely();
            }
          }, 2000);
        }
      }
    };

    recognition.onerror = (event) => {
      if (event.error === 'no-speech') return;
      console.warn('[VOICE] recognition error:', event.error);
      if (event.error === 'not-allowed' || event.error === 'service-not-allowed') {
        setErrorMessage('Microphone permission is required for Voice Mode.');
        turnVoiceOff();
        setVoiceState('ERROR');
      }
    };

    recognition.onend = () => {
      isRecognitionActiveRef.current = false;
      console.log('[VOICE] recognition instance ended');

      if (
        voiceEnabledRef.current &&
        shouldRestartRef.current &&
        !isSpeakingRef.current &&
        !isProcessingRef.current
      ) {
        console.log('[VOICE] restarting recognition safely from onend');
        startRecognitionSafely();
      } else {
        if (!voiceEnabledRef.current) {
          setVoiceState('OFF');
        }
      }
    };

    recognitionRef.current = recognition;

    return () => {
      turnVoiceOff();
    };
  }, []);

  const toggleVoiceMode = () => {
    if (isVoiceOn) {
      turnVoiceOff();
    } else {
      turnVoiceOn();
    }
  };

  const toggleAssistantVoice = () => {
    setIsTtsEnabled((prev) => !prev);
  };

  const getBadgeStyle = () => {
    switch (voiceState) {
      case 'LISTENING':
        return 'bg-emerald-100 text-emerald-800 border-emerald-300 animate-pulse';
      case 'PROCESSING':
        return 'bg-amber-100 text-amber-800 border-amber-300';
      case 'SPEAKING':
      case 'COMMAND RECOGNIZED':
      case 'ACTION COMPLETED':
        return 'bg-blue-100 text-blue-800 border-blue-300';
      case 'ERROR':
        return 'bg-rose-100 text-rose-800 border-rose-300';
      case 'OFF':
      default:
        return 'bg-slate-100 text-slate-600 border-slate-200';
    }
  };

  return (
    <div className="bg-white rounded-2xl shadow-sm border border-slate-200 p-6 transition-all">
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Toggle Controls */}
        <div className="flex items-center gap-4">
          <button
            onClick={toggleVoiceMode}
            className={`relative flex items-center justify-center w-16 h-16 rounded-full transition-all duration-300 shadow-md ${
              isVoiceOn
                ? 'bg-emerald-600 hover:bg-emerald-700 text-white ring-4 ring-emerald-100'
                : 'bg-slate-800 hover:bg-slate-900 text-white'
            }`}
            title={isVoiceOn ? 'Turn Voice Mode OFF' : 'Turn Voice Mode ON'}
          >
            {isVoiceOn ? (
              <Mic className="w-8 h-8 animate-bounce" />
            ) : (
              <MicOff className="w-8 h-8" />
            )}
            {isVoiceOn && (
              <span className="absolute -top-1 -right-1 flex h-4 w-4">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-4 w-4 bg-emerald-500"></span>
              </span>
            )}
          </button>

          <div>
            <div className="flex items-center gap-3">
              <h2 className="text-xl font-bold text-slate-800">
                Voice Listening: {isVoiceOn ? 'ON' : 'OFF'}
              </h2>
              <button
                onClick={toggleAssistantVoice}
                className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1.5 rounded-xl border transition-all ${
                  isTtsEnabled
                    ? 'bg-indigo-50 text-indigo-700 border-indigo-200 hover:bg-indigo-100 shadow-sm'
                    : 'bg-slate-100 text-slate-500 border-slate-200 hover:bg-slate-200'
                }`}
                title={isTtsEnabled ? 'Assistant Voice: ON' : 'Assistant Voice: OFF'}
              >
                {isTtsEnabled ? <Volume2 className="w-4 h-4 text-indigo-600" /> : <VolumeX className="w-4 h-4 text-slate-400" />}
                <span>Assistant Voice: {isTtsEnabled ? 'ON' : 'OFF'}</span>
              </button>
            </div>
            <p className="text-sm text-slate-500 mt-1">
              {isVoiceOn
                ? 'Continuously listening... Say commands like "Add milk", "Add shampoo", "Remove bread"'
                : 'Click to start voice listening'}
            </p>
          </div>
        </div>

        {/* State Badge */}
        <div className="flex items-center gap-2">
          <span className={`px-4 py-2 rounded-full border text-xs font-semibold uppercase tracking-wider flex items-center gap-2 ${getBadgeStyle()}`}>
            {voiceState === 'PROCESSING' && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            {voiceState === 'LISTENING' && <Sparkles className="w-3.5 h-3.5" />}
            {voiceState === 'SPEAKING' && <Volume2 className="w-3.5 h-3.5 animate-pulse" />}
            {voiceState}
          </span>
        </div>
      </div>

      {/* Transcript & Error Box */}
      {lastTranscript && (
        <div className="mt-4 p-3 bg-slate-50 border border-slate-200 rounded-xl text-sm font-medium text-slate-700 flex items-center gap-2">
          <span className="text-indigo-600 font-bold">Heard:</span> "{lastTranscript}"
        </div>
      )}

      {errorMessage && (
        <div className="mt-4 p-3 bg-rose-50 border border-rose-200 rounded-xl text-sm font-medium text-rose-700 flex items-center gap-2">
          <AlertCircle className="w-4 h-4 text-rose-600 flex-shrink-0" />
          {errorMessage}
        </div>
      )}
    </div>
  );
};
