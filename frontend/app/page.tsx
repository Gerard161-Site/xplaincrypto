'use client';

import React, { useState, useEffect } from "react";
import io from "socket.io-client";
import Image from "next/image";

export default function Home() {
  const [projectName, setProjectName] = useState("");
  const [progress, setProgress] = useState<string[]>([]);
  const [reportUrl, setReportUrl] = useState("");

  useEffect(() => {
    const socket = io("http://localhost:8000");
    socket.on("connect", () => console.log("Connected to WebSocket"));
    socket.on("message", (msg) => {
      setProgress((prev) => [...prev, msg]);
    });
    socket.on("data", (data) => {
      setProgress((prev) => [...prev, data.status]);
      setReportUrl(data.final_report);
    });
    socket.on("error", (err) => {
      setProgress((prev) => [...prev, `Error: ${err}`]);
    });

    return () => {
      socket.disconnect();
    };
  }, []);

  const handleGenerate = () => {
    setProgress([]); // Clear previous logs
    setReportUrl(""); // Reset download link
    const socket = io("http://localhost:8000");
    socket.emit("message", { project_name: projectName });
  };

  return (
    <div className="grid grid-rows-[20px_1fr_20px] items-center justify-items-center min-h-screen p-8 pb-20 gap-16 sm:p-20">
      <main className="flex flex-col gap-[32px] row-start-2 items-center sm:items-start w-full max-w-md">
        <Image
          className="dark:invert"
          src="/next.svg"
          alt="Next.js logo"
          width={180}
          height={38}
          priority
        />
        <h1 className="text-2xl font-bold mb-4">XplainCrypto</h1>
        
        <div className="w-full space-y-4">
          <input
            type="text"
            value={projectName}
            onChange={(e) => setProjectName(e.target.value)}
            placeholder="Enter project name (e.g., Solana)"
            className="w-full p-2 border rounded bg-background text-foreground"
          />
          
          <button
            onClick={handleGenerate}
            className="w-full p-2 bg-foreground text-background rounded hover:bg-[#383838] dark:hover:bg-[#ccc] transition-colors"
          >
            Generate Report
          </button>

          <div className="mt-4 max-h-64 overflow-y-auto border p-2 rounded bg-background/[.05] dark:bg-white/[.06]">
            {progress.map((msg, idx) => (
              <p key={idx} className="text-sm text-foreground/80">{msg}</p>
            ))}
          </div>

          {reportUrl && (
            <a
              href={`http://localhost:8000/${reportUrl}`}
              download
              className="mt-4 block text-foreground underline hover:no-underline"
            >
              Download Report
            </a>
          )}
        </div>

        <div className="flex gap-4 items-center flex-col sm:flex-row">
          <a
            className="rounded-full border border-solid border-transparent transition-colors flex items-center justify-center bg-foreground text-background gap-2 hover:bg-[#383838] dark:hover:bg-[#ccc] font-medium text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5 sm:w-auto"
            href="https://vercel.com/new?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Image
              className="dark:invert"
              src="/vercel.svg"
              alt="Vercel logomark"
              width={20}
              height={20}
            />
            Deploy now
          </a>
          <a
            className="rounded-full border border-solid border-black/[.08] dark:border-white/[.145] transition-colors flex items-center justify-center hover:bg-[#f2f2f2] dark:hover:bg-[#1a1a1a] hover:border-transparent font-medium text-sm sm:text-base h-10 sm:h-12 px-4 sm:px-5 w-full sm:w-auto md:w-[158px]"
            href="https://nextjs.org/docs?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
            target="_blank"
            rel="noopener noreferrer"
          >
            Read our docs
          </a>
        </div>
      </main>
      <footer className="row-start-3 flex gap-[24px] flex-wrap items-center justify-center">
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://nextjs.org/learn?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/file.svg"
            alt="File icon"
            width={16}
            height={16}
          />
          Learn
        </a>
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://vercel.com/templates?framework=next.js&utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/window.svg"
            alt="Window icon"
            width={16}
            height={16}
          />
          Examples
        </a>
        <a
          className="flex items-center gap-2 hover:underline hover:underline-offset-4"
          href="https://nextjs.org?utm_source=create-next-app&utm_medium=appdir-template-tw&utm_campaign=create-next-app"
          target="_blank"
          rel="noopener noreferrer"
        >
          <Image
            aria-hidden
            src="/globe.svg"
            alt="Globe icon"
            width={16}
            height={16}
          />
          Go to nextjs.org →
        </a>
      </footer>
    </div>
  );
}
