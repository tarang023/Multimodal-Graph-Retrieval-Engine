"use client";

import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Sparkles, ChevronDown, ChevronUp, CheckCircle2 } from "lucide-react";

export default function ChatInterface({ documentData, isProcessing }) {
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isAccordionOpen, setIsAccordionOpen] = useState(true);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  useEffect(() => {
    if (documentData && messages.length === 0) {
      setMessages([{
        role: "assistant",
        content: "I've analyzed the document. You can now ask me any questions about it."
      }]);
    } else if (!documentData) {
      setMessages([]);
    }
  }, [documentData]);

  const sendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || isLoading) return;

    const userMessage = inputValue.trim();
    setInputValue("");
    setMessages(prev => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const res = await fetch("http://localhost:8000/analyze", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          question: userMessage,
          expense_data: documentData ?? {},   // Must match AnalyzeRequest.expense_data
          employee_id: "EMP-001",             // TODO: replace with real auth user id
        }),
      });
      
      if (!res.ok) throw new Error("Request failed");
      const data = await res.json();
      
      // /analyze now returns explanation and sources after Gemini reasoning
      let responseText = data.explanation || "Processed successfully.";
      if (data.sources && data.sources.length > 0) {
        responseText += "\n\n**Sources Cited:**\n- " + data.sources.join("\n- ");
      }
      
      setMessages(prev => [...prev, { role: "assistant", content: responseText }]);
      setIsLoading(false);
    } catch (err) {
      console.error("Chat API error:", err);
      // Fallback for demo
      setTimeout(() => {
        setMessages(prev => [...prev, { 
          role: "assistant", 
          content: "I'm currently running in offline demo mode. If the backend at localhost:8000 was running, I would have answered: '" + userMessage + "'" 
        }]);
        setIsLoading(false);
      }, 1000);
    }
  };

  // State A: Initial
  if (!documentData && !isProcessing) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-slate-50/50 p-8 text-center">
        <div className="w-20 h-20 bg-blue-100 rounded-full flex items-center justify-center mb-6 shadow-inner">
          <Sparkles className="w-10 h-10 text-blue-600" />
        </div>
        <h2 className="text-2xl font-bold text-slate-800 mb-2">Graph-RAG Assistant</h2>
        <p className="text-slate-500 max-w-sm leading-relaxed">
          Upload a financial document or receipt on the left to begin extraction and semantic analysis.
        </p>
      </div>
    );
  }

  // State A: Processing
  if (isProcessing) {
    return (
      <div className="h-full flex flex-col items-center justify-center bg-white p-8 text-center">
        <div className="relative w-20 h-20 mb-6">
          <div className="absolute inset-0 border-4 border-blue-100 rounded-full"></div>
          <div className="absolute inset-0 border-4 border-blue-600 rounded-full border-t-transparent animate-spin"></div>
          <Bot className="w-8 h-8 text-blue-600 absolute inset-0 m-auto" />
        </div>
        <h2 className="text-xl font-semibold text-slate-800 mb-2">Analyzing Document...</h2>
        <p className="text-slate-500 text-sm">Extracting entities and building knowledge graph</p>
      </div>
    );
  }

  // State B: Processed
  return (
    <div className="h-full flex flex-col bg-white">
      {/* Header / Extracted Data Accordion */}
      <div className="border-b border-slate-200 shadow-sm z-10">
        <button 
          onClick={() => setIsAccordionOpen(!isAccordionOpen)}
          className="w-full flex items-center justify-between p-4 bg-slate-50 hover:bg-slate-100 transition-colors"
        >
          <div className="flex items-center gap-2">
            <CheckCircle2 className="w-5 h-5 text-emerald-500" />
            <span className="font-semibold text-slate-700">Extracted Information</span>
          </div>
          {isAccordionOpen ? <ChevronUp className="w-5 h-5 text-slate-400" /> : <ChevronDown className="w-5 h-5 text-slate-400" />}
        </button>
        
        {isAccordionOpen && (
          <div className="p-4 grid grid-cols-2 gap-4 bg-white">
            {Object.entries(documentData).map(([key, value]) => (
              <div key={key} className="bg-slate-50 rounded-lg p-3 border border-slate-100">
                <p className="text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">{key}</p>
                <p className="font-medium text-slate-800 truncate">{value}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Chat History */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6 bg-slate-50/50">
        {messages.map((msg, idx) => (
          <div key={idx} className={`flex gap-3 max-w-[85%] ${msg.role === "user" ? "ml-auto flex-row-reverse" : ""}`}>
            <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${
              msg.role === "user" ? "bg-blue-600" : "bg-emerald-500"
            }`}>
              {msg.role === "user" ? (
                <User className="w-5 h-5 text-white" />
              ) : (
                <Bot className="w-5 h-5 text-white" />
              )}
            </div>
            <div className={`p-3 rounded-2xl ${
              msg.role === "user" 
                ? "bg-blue-600 text-white rounded-tr-sm" 
                : "bg-white border border-slate-200 text-slate-700 rounded-tl-sm shadow-sm"
            }`}>
              <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-3 max-w-[85%]">
            <div className="w-8 h-8 rounded-full bg-emerald-500 flex items-center justify-center shrink-0">
              <Bot className="w-5 h-5 text-white" />
            </div>
            <div className="p-4 bg-white border border-slate-200 rounded-2xl rounded-tl-sm shadow-sm flex gap-1.5 items-center">
              <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:-0.3s]"></div>
              <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce [animation-delay:-0.15s]"></div>
              <div className="w-2 h-2 bg-slate-300 rounded-full animate-bounce"></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="p-4 bg-white border-t border-slate-200">
        <form onSubmit={sendMessage} className="relative flex items-center">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="Ask a question about this document..."
            className="w-full pl-4 pr-12 py-3 bg-slate-50 border border-slate-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition-all shadow-sm text-slate-900"
            disabled={isLoading}
          />
          <button 
            type="submit" 
            disabled={!inputValue.trim() || isLoading}
            className="absolute right-2 p-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            <Send className="w-4 h-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
