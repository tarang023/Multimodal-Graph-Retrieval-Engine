"use client";

import { useState, useCallback } from "react";
import { useDropzone } from "react-dropzone";
import { UploadCloud, FileText, Image as ImageIcon, Loader2 } from "lucide-react";

export default function UploadZone({ onUploadStart, onUploadComplete }) {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [receiptData, setReceiptData] = useState(null);
  const [errorMsg, setErrorMsg] = useState(null);

  const onDrop = useCallback(async (acceptedFiles) => {
    const selectedFile = acceptedFiles[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    
    // Create preview for images
    if (selectedFile.type.startsWith("image/")) {
      setPreview(URL.createObjectURL(selectedFile));
    } else {
      setPreview(null);
    }

    setUploading(true);
    setErrorMsg(null);
    setReceiptData(null);
    onUploadStart();

    const formData = new FormData();
    formData.append("file", selectedFile);
    
    try {
      const res = await fetch("http://localhost:8000/upload", {
        method: "POST",
        body: formData,
      });
      if (!res.ok) throw new Error("Upload failed (Status: " + res.status + ")");
      const data = await res.json();
      
      setReceiptData(data.data);
      onUploadComplete(data.data);
    } catch (err) {
      console.error("API error:", err);
      setErrorMsg("Error processing document. Please try again.");
      onUploadComplete(null);
    } finally {
      setUploading(false);
    }
  }, [onUploadStart, onUploadComplete]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({ 
    onDrop,
    accept: {
      'image/*': ['.jpeg', '.jpg', '.png'],
      'application/pdf': ['.pdf']
    },
    maxFiles: 1
  });

  return (
    <div className="h-full flex flex-col">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-slate-800">Document Upload</h1>
        <p className="text-slate-500 text-sm mt-1">Upload a financial document or receipt to analyze.</p>
      </div>

      {!file ? (
        <div 
          {...getRootProps()} 
          className={`flex-1 border-2 border-dashed rounded-xl flex flex-col items-center justify-center p-8 transition-colors cursor-pointer
            ${isDragActive ? 'border-blue-500 bg-blue-50' : 'border-slate-300 bg-slate-50 hover:bg-slate-100 hover:border-slate-400'}`}
        >
          <input {...getInputProps()} />
          <UploadCloud className={`w-16 h-16 mb-4 ${isDragActive ? 'text-blue-500' : 'text-slate-400'}`} />
          <p className="text-lg font-medium text-slate-700">
            {isDragActive ? "Drop the file here..." : "Drag & drop your document here"}
          </p>
          <p className="text-sm text-slate-500 mt-2">Supports PDF, JPG, PNG up to 10MB</p>
          
          <button className="mt-6 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white font-medium rounded-lg shadow-sm transition-colors">
            Browse Files
          </button>
        </div>
      ) : (
        <div className="flex-1 border rounded-xl bg-white shadow-sm overflow-hidden flex flex-col">
          <div className="p-4 border-b bg-slate-50 flex items-center justify-between">
            <div className="flex items-center gap-3">
              {file.type.startsWith("image/") ? (
                <ImageIcon className="w-5 h-5 text-blue-500" />
              ) : (
                <FileText className="w-5 h-5 text-rose-500" />
              )}
              <span className="font-medium text-slate-700 truncate max-w-[300px]">
                {file.name}
              </span>
            </div>
            <button 
              onClick={() => {
                setFile(null);
                setPreview(null);
                setReceiptData(null);
                setErrorMsg(null);
                onUploadComplete(null);
              }}
              className="text-sm text-slate-500 hover:text-slate-700"
            >
              Clear
            </button>
          </div>
          
          <div className="flex-1 p-6 flex items-start justify-center bg-slate-100 relative overflow-y-auto">
            {uploading && (
              <div className="absolute inset-0 bg-white/80 backdrop-blur-sm flex flex-col items-center justify-center z-10">
                <Loader2 className="w-10 h-10 text-blue-600 animate-spin mb-4" />
                <p className="text-slate-700 font-medium animate-pulse">Processing document...</p>
                <div className="w-64 h-2 bg-slate-200 rounded-full mt-4 overflow-hidden">
                  <div className="h-full bg-blue-600 rounded-full w-1/2 animate-[pulse_2s_ease-in-out_infinite]"></div>
                </div>
              </div>
            )}
            
            {errorMsg && (
              <div className="absolute inset-0 bg-rose-50 flex flex-col items-center justify-center z-10 border border-rose-200">
                <p className="text-rose-600 font-semibold">{errorMsg}</p>
                <button 
                  onClick={() => setErrorMsg(null)}
                  className="mt-4 px-4 py-2 bg-rose-100 hover:bg-rose-200 text-rose-700 rounded transition-colors"
                >
                  Dismiss
                </button>
              </div>
            )}
            
            <div className="flex gap-6 w-full max-w-4xl h-full items-start">
              {/* Left Column: Image Preview */}
              <div className="flex-1 h-full flex flex-col justify-start">
                {preview ? (
                  <img src={preview} alt="Document Preview" className="max-w-full rounded shadow object-contain" />
                ) : (
                  <div className="flex flex-col items-center text-slate-400 justify-center h-full">
                    <FileText className="w-24 h-24 mb-4 opacity-50" />
                    <p>Document Selected</p>
                  </div>
                )}
              </div>

              {/* Right Column: Receipt Summary Card */}
              {receiptData && (
                <div className="flex-[1.2] bg-white rounded-xl shadow-lg border border-slate-200 p-6 flex flex-col max-h-full overflow-y-auto">
                  <h3 className="text-lg font-bold text-slate-800 mb-4 border-b pb-2">Receipt Summary</h3>
                  
                  {/* Top Level Grid */}
                  <div className="grid grid-cols-2 gap-4 mb-6">
                    <div>
                      <p className="text-xs text-slate-400 uppercase font-semibold">Vendor</p>
                      <p className="text-sm text-slate-900 font-medium">{receiptData.vendor || "N/A"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400 uppercase font-semibold">Total Amount</p>
                      <p className="text-sm text-emerald-600 font-bold">{receiptData.currency} {receiptData.amount}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400 uppercase font-semibold">Tax</p>
                      <p className="text-sm text-slate-700">{receiptData.currency} {receiptData.tax_amount || "0.00"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400 uppercase font-semibold">Date</p>
                      <p className="text-sm text-slate-700">{receiptData.date || "N/A"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400 uppercase font-semibold">Category</p>
                      <p className="text-sm text-slate-700">{receiptData.category || "N/A"}</p>
                    </div>
                    <div>
                      <p className="text-xs text-slate-400 uppercase font-semibold">Type / Method</p>
                      <p className="text-sm text-slate-700">
                        {receiptData.document_type || "N/A"} • {receiptData.payment_method || "N/A"}
                      </p>
                    </div>
                  </div>

                  {/* Line Items Table */}
                  {receiptData.is_itemized && receiptData.line_items && receiptData.line_items.length > 0 && (
                    <div className="mb-6">
                      <p className="text-xs text-slate-400 uppercase font-semibold mb-2">Line Items</p>
                      <div className="border border-slate-200 rounded-lg overflow-hidden">
                        <table className="w-full text-left text-sm">
                          <thead className="bg-slate-50 border-b border-slate-200">
                            <tr>
                              <th className="py-2 px-3 text-slate-600 font-medium">Description</th>
                              <th className="py-2 px-3 text-slate-600 font-medium text-right">Amount</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-100">
                            {receiptData.line_items.map((item, idx) => (
                              <tr key={idx} className="hover:bg-slate-50">
                                <td className="py-2 px-3 text-slate-800">{item.description}</td>
                                <td className="py-2 px-3 text-slate-800 text-right font-medium">
                                  {receiptData.currency} {item.amount}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  )}

                  {/* Additional Notes */}
                  {receiptData.additional_notes && (
                    <div className="mt-auto bg-amber-50 rounded p-3 border border-amber-100">
                      <p className="text-xs text-amber-700 uppercase font-semibold mb-1">Notes</p>
                      <p className="text-sm text-amber-900 italic">{receiptData.additional_notes}</p>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
