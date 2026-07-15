"use client";

import UploadZone from "@/components/UploadZone";
import ChatInterface from "@/components/ChatInterface";
import { useState } from "react";

export default function Home() {
  const [documentData, setDocumentData] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  return (
    <main className="flex h-screen w-full bg-slate-50 overflow-hidden">
      {/* Left Panel - 60% */}
      <section className="w-[60%] h-full p-6 border-r border-slate-200">
        <UploadZone 
          onUploadStart={() => setIsProcessing(true)}
          onUploadComplete={(data) => {
            setDocumentData(data);
            setIsProcessing(false);
          }}
        />
      </section>

      {/* Right Panel - 40% */}
      <section className="w-[40%] h-full bg-white shadow-[-4px_0_24px_-12px_rgba(0,0,0,0.1)] z-10 relative">
        <ChatInterface 
          documentData={documentData} 
          isProcessing={isProcessing} 
        />
      </section>
    </main>
  );
}
