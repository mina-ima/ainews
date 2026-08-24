"use client";

import {
  useCallback,
  useEffect,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
}

interface SpeechRecognitionEvent extends Event {
  results: SpeechRecognitionResultList;
  resultIndex: number;
}

interface SpeechRecognitionErrorEvent extends Event {
  error: string;
}

interface SpeechRecognitionResultList {
  length: number;
  item(index: number): SpeechRecognitionResult;
  [index: number]: SpeechRecognitionResult;
}

interface SpeechRecognitionResult {
  isFinal: boolean;
  length: number;
  item(index: number): SpeechRecognitionAlternative;
  [index: number]: SpeechRecognitionAlternative;
}

interface SpeechRecognitionAlternative {
  transcript: string;
  confidence: number;
}

interface WindowWithSpeechRecognition extends Window {
  SpeechRecognition?: new () => SpeechRecognition;
  webkitSpeechRecognition?: new () => SpeechRecognition;
}

interface SpeechRecognition extends EventTarget {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  start(): void;
  stop(): void;
  abort(): void;
  onstart?: (event: Event) => void;
  onend?: (event: Event) => void;
  onresult?: (event: SpeechRecognitionEvent) => void;
  onerror?: (event: SpeechRecognitionErrorEvent) => void;
}

const STORAGE_KEY = "ainews-tts";

// 変化しない値なので購読は空。サーバー側スナップショットは false（SSR時に window が無い）
const subscribeNever = () => () => {};
const getMicSupported = () =>
  Boolean(
    (window as WindowWithSpeechRecognition).SpeechRecognition ||
      (window as WindowWithSpeechRecognition).webkitSpeechRecognition
  );
const getTtsSupported = () => Boolean(window.speechSynthesis);
const getServerFalse = () => false;

// 読み上げ設定は localStorage が持つ外部状態。プライベートモード等で
// localStorage 自体が例外を投げうるので、読み書きとも失敗時は既定値に倒す
const ttsListeners = new Set<() => void>();
const subscribeTtsEnabled = (onChange: () => void) => {
  ttsListeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    ttsListeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
};
// localStorage が使えない環境（プライベートモード等）でセッション内だけ保持する値
let ttsFallback: boolean | null = null;
const getTtsEnabled = () => {
  if (ttsFallback !== null) return ttsFallback;
  try {
    return localStorage.getItem(STORAGE_KEY) !== "false";
  } catch {
    return true;
  }
};
const getTtsEnabledServer = () => true;
const storeTtsEnabled = (value: boolean) => {
  try {
    localStorage.setItem(STORAGE_KEY, String(value));
    ttsFallback = null;
  } catch {
    // 保存できないので、次のリロードまではメモリ側の値を正とする
    ttsFallback = value;
  }
  ttsListeners.forEach((notify) => notify());
};

export default function NewsChat({ date }: { date: string }) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [interimTranscript, setInterimTranscript] = useState("");
  const [isListening, setIsListening] = useState(false);
  const ttsEnabled = useSyncExternalStore(
    subscribeTtsEnabled,
    getTtsEnabled,
    getTtsEnabledServer
  );
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const micSupported = useSyncExternalStore(
    subscribeNever,
    getMicSupported,
    getServerFalse
  );
  const ttsSupported = useSyncExternalStore(
    subscribeNever,
    getTtsSupported,
    getServerFalse
  );

  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const handleSendRef = useRef<() => Promise<void> | void | null>(null);
  const isSubmittingRef = useRef(false);

  const startSpeaking = useCallback(
    (text: string) => {
      if (!window.speechSynthesis || !ttsEnabled) return;

      window.speechSynthesis.cancel();

      utteranceRef.current = new SpeechSynthesisUtterance(text);
      utteranceRef.current.lang = "ja-JP";

      const voices = window.speechSynthesis.getVoices();
      const japaneseVoice = voices.find((v) => v.lang.startsWith("ja"));
      if (japaneseVoice) {
        utteranceRef.current.voice = japaneseVoice;
      }

      utteranceRef.current.onstart = () => {
        setIsSpeaking(true);
      };

      utteranceRef.current.onend = () => {
        setIsSpeaking(false);
      };

      utteranceRef.current.onerror = () => {
        setIsSpeaking(false);
      };

      setIsSpeaking(true);
      window.speechSynthesis.speak(utteranceRef.current);
    },
    [ttsEnabled]
  );

  const handleSend = useCallback(async () => {
    if (isSubmittingRef.current) return;

    const text = (input + interimTranscript).trim();
    if (!text || loading) return;

    isSubmittingRef.current = true;

    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }

    const userMessage: ChatMessage = {
      role: "user",
      content: text,
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setInterimTranscript("");
    setLoading(true);
    setError(null);

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          date,
          messages: [...messages, userMessage],
        }),
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error || "エラーが発生しました");
      }

      const data = await response.json();
      const assistantMessage: ChatMessage = {
        role: "assistant",
        content: data.answer,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      if (ttsEnabled && data.answer) {
        startSpeaking(data.answer);
      }
    } catch (err) {
      const errorMsg =
        err instanceof Error ? err.message : "エラーが発生しました";
      setError(errorMsg);
    } finally {
      setLoading(false);
      isSubmittingRef.current = false;
    }
  }, [input, interimTranscript, loading, messages, date, ttsEnabled, isListening, startSpeaking]);

  // Store handleSend in ref to avoid effect re-initialization
  useEffect(() => {
    handleSendRef.current = handleSend;
  }, [handleSend]);

  const stopSpeaking = () => {
    if (window.speechSynthesis) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
    }
  };

  const startListening = () => {
    if (recognitionRef.current && !isListening) {
      setInterimTranscript("");
      recognitionRef.current.start();
    }
  };

  const stopListening = () => {
    if (recognitionRef.current && isListening) {
      recognitionRef.current.stop();
    }
  };

  useEffect(() => {
    const SpeechRecognitionClass =
      (window as WindowWithSpeechRecognition).SpeechRecognition ||
      (window as WindowWithSpeechRecognition).webkitSpeechRecognition;

    if (SpeechRecognitionClass) {
      recognitionRef.current = new SpeechRecognitionClass();
      recognitionRef.current.lang = "ja-JP";
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = true;

      recognitionRef.current.onstart = () => {
        setIsListening(true);
        setError(null);
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current.onresult = (event: SpeechRecognitionEvent) => {
        let interim = "";
        let hasFinal = false;

        for (let i = event.resultIndex; i < event.results.length; i++) {
          const transcript = event.results[i][0].transcript;
          if (event.results[i].isFinal) {
            setInput((prev) => prev + transcript);
            hasFinal = true;
          } else {
            interim += transcript;
          }
        }
        setInterimTranscript(interim);

        if (hasFinal && interim === "") {
          setTimeout(() => {
            if (handleSendRef.current) {
              handleSendRef.current();
            }
          }, 100);
        }
      };

      recognitionRef.current.onerror = () => {
        setError("音声認識エラーが発生しました");
        setIsListening(false);
      };
    }

    return () => {
      if (recognitionRef.current) {
        recognitionRef.current.abort();
      }
      if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
      }
    };
  }, []);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const handleMicToggle = () => {
    if (isListening) {
      stopListening();
    } else {
      startListening();
    }
  };

  return (
    <div className="mt-12 border-t border-slate-700 pt-8">
      <h2 className="text-2xl font-bold mb-6 text-slate-100">
        このニュースについて話す
      </h2>

      <div className="space-y-4 mb-6 max-h-96 overflow-y-auto">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`p-4 rounded-lg ${
              msg.role === "user"
                ? "bg-blue-900 text-blue-50 ml-8"
                : "bg-slate-800 text-slate-100 mr-8"
            }`}
          >
            <div className="text-sm font-semibold mb-1">
              {msg.role === "user" ? "あなた" : "解説者"}
            </div>
            <div className="text-sm leading-relaxed">{msg.content}</div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </div>

      {error && (
        <div className="mb-4 p-3 rounded-lg bg-red-900 text-red-100 text-sm">
          {error}
        </div>
      )}

      {interimTranscript && (
        <div className="mb-4 p-3 rounded-lg bg-slate-700 text-slate-200 text-sm italic">
          {interimTranscript}
        </div>
      )}

      {loading && (
        <div className="mb-4 p-3 rounded-lg bg-slate-700 text-slate-300 text-sm">
          考えています…
        </div>
      )}

      {isSpeaking && (
        <div className="mb-4 p-3 rounded-lg bg-slate-700 text-slate-300 text-sm">
          話しています…
        </div>
      )}

      <div className="space-y-3">
        <textarea
          data-testid="chat-input"
          value={input + interimTranscript}
          onChange={(e) => {
            const newVal = e.target.value;
            if (newVal.startsWith(interimTranscript)) {
              setInput(newVal.slice(interimTranscript.length));
            } else {
              setInput(newVal);
            }
          }}
          disabled={loading}
          className="w-full px-4 py-3 rounded-lg bg-slate-800 text-slate-100 border border-slate-700 focus:border-blue-500 focus:outline-none resize-none"
          rows={2}
          placeholder="質問を入力してください…"
        />

        <div className="flex gap-2">
          <button
            onClick={handleSend}
            disabled={loading || (!input && !interimTranscript)}
            className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 disabled:bg-slate-700 text-white text-sm font-medium transition"
          >
            {loading ? "送信中…" : "送信"}
          </button>

          {micSupported && (
            <button
              onClick={handleMicToggle}
              disabled={loading}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                isListening
                  ? "bg-red-600 hover:bg-red-700 text-white"
                  : "bg-slate-700 hover:bg-slate-600 text-slate-100"
              } disabled:bg-slate-800 disabled:text-slate-500`}
              title={isListening ? "リッスニング中..." : "マイクで入力"}
            >
              🎤 {isListening ? "停止" : "音声入力"}
            </button>
          )}

          {ttsSupported && (
            <>
              <button
                onClick={() => storeTtsEnabled(!ttsEnabled)}
                className={`px-4 py-2 rounded-lg text-sm font-medium transition ${
                  ttsEnabled
                    ? "bg-slate-600 hover:bg-slate-500 text-white"
                    : "bg-slate-800 hover:bg-slate-700 text-slate-300"
                }`}
                title={ttsEnabled ? "読み上げON" : "読み上げOFF"}
              >
                🔊 {ttsEnabled ? "ON" : "OFF"}
              </button>

              {isSpeaking && (
                <button
                  onClick={stopSpeaking}
                  className="px-4 py-2 rounded-lg bg-orange-600 hover:bg-orange-700 text-white text-sm font-medium transition"
                >
                  ⏹ 停止
                </button>
              )}
            </>
          )}
        </div>
      </div>

      {!micSupported && (
        <div className="mt-3 p-3 rounded-lg bg-slate-800 text-slate-400 text-xs">
          注: このブラウザは音声入力に対応していません
        </div>
      )}
    </div>
  );
}
