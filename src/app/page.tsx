"use client";

import { useEffect, useState } from "react";

export default function Dashboard() {
  const [status, setStatus] = useState<any>(null);
  const [episodes, setEpisodes] = useState<any[]>([]);
  const [search, setSearch] = useState("");
  const [triggering, setTriggering] = useState(false);

  useEffect(() => {
    fetchStatus();
    fetchEpisodes();
    const interval = setInterval(fetchStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const fetchStatus = async () => {
    try {
      const res = await fetch("/status.json");
      const data = await res.json();
      setStatus(data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchEpisodes = async () => {
    try {
      const res = await fetch("/episodes/index.json");
      const data = await res.json();
      // adapt to previous API shape
      const adapted = data.map((ep: any) => ({
        id: ep.id,
        audioUrl: ep.audio,
        date: ep.date,
        transcript: ep.transcript || []
      }));
      setEpisodes(adapted);
    } catch (e) {
      console.error(e);
    }
  };

  const handleTrigger = async () => {
    // For GitHub Pages deployments we cannot safely call GitHub REST from client-side.
    // Open the Actions workflow page so the user can manually dispatch.
    const repo = process.env.NEXT_PUBLIC_GITHUB_REPO || '';
    if (!repo) {
      alert('Set NEXT_PUBLIC_GITHUB_REPO at build-time to enable manual trigger link.');
      return;
    }
    const url = `https://github.com/${repo}/actions/workflows/generate.yml`;
    window.open(url, '_blank');
  };

  const filteredEpisodes = episodes.filter(ep => {
    if (!search) return true;
    if (!ep.transcript) return false;
    return ep.transcript.some((t: any) => 
      t.text.toLowerCase().includes(search.toLowerCase())
    );
  });

  return (
    <div className="min-h-screen bg-neutral-900 text-white p-8 font-sans">
      <div className="max-w-4xl mx-auto space-y-8">
        <header className="flex justify-between items-center bg-neutral-800 p-6 rounded-xl shadow-lg">
          <h1 className="text-3xl font-extrabold text-orange-400 tracking-tight">🏏 IPL Pulse 2026</h1>
          <button 
            disabled={triggering}
            onClick={handleTrigger}
            className="bg-orange-500 hover:bg-orange-600 disabled:bg-neutral-600 disabled:text-neutral-400 text-white px-6 py-2 rounded-lg font-bold transition-colors shadow-md"
          >
            {triggering ? "Triggering..." : "Generate Episode"}
          </button>
        </header>

        {status && (
          <section className="bg-neutral-800 p-6 rounded-xl shadow-lg border border-neutral-700">
            <h2 className="text-xl font-bold mb-4 flex items-center gap-2">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-orange-500"></span>
              </span>
              Pipeline Status
            </h2>
            <div className="mb-2 flex justify-between text-sm font-medium text-neutral-300">
              <span>{status.phase} - {status.message}</span>
              <span>{status.progress}%</span>
            </div>
            <div className="w-full bg-neutral-700 rounded-full h-3 overflow-hidden">
              <div 
                className="bg-orange-500 h-3 rounded-full transition-all duration-700 ease-in-out"
                style={{ width: `${Math.max(0, Math.min(100, status.progress))}%` }}
              ></div>
            </div>
            {status.updated_at && (
              <div className="text-xs text-neutral-400 mt-3 text-right">
                Last updated: {new Date(status.updated_at).toLocaleString()}
              </div>
            )}
          </section>
        )}

        <section className="space-y-6">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
            <h2 className="text-2xl font-bold text-neutral-100">Episode Archive</h2>
            <input 
              type="text" 
              placeholder="Search transcripts..." 
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="bg-neutral-800 border border-neutral-700 focus:border-orange-500 focus:ring-1 focus:ring-orange-500 px-4 py-2 rounded-lg text-white w-full sm:w-auto shadow-sm outline-none transition-all"
            />
          </div>

          <div className="space-y-4">
            {filteredEpisodes.length === 0 ? (
              <div className="bg-neutral-800 p-8 rounded-xl text-center text-neutral-400 border border-neutral-700">
                No episodes found matching your search.
              </div>
            ) : (
              filteredEpisodes.map((ep: any) => (
                <div key={ep.id} className="bg-neutral-800 p-6 rounded-xl space-y-4 border border-neutral-700 shadow-md">
                  <div className="flex flex-col md:flex-row justify-between items-center gap-4">
                    <h3 className="text-lg font-bold text-orange-300">
                      {ep.date ? `Episode: ${ep.date}` : 'Latest Episode'}
                    </h3>
                    <audio controls src={ep.audioUrl} className="w-full md:w-2/3 max-w-md bg-neutral-900 rounded-full"></audio>
                  </div>
                  
                  {search && ep.transcript && (
                    <div className="bg-neutral-900 p-4 rounded-lg text-sm space-y-3 max-h-60 overflow-y-auto border border-neutral-800">
                      <p className="text-orange-400 font-semibold mb-2 sticky top-0 bg-neutral-900 pb-2 border-b border-neutral-800">Transcript Matches:</p>
                      {ep.transcript
                        .filter((t: any) => t.text.toLowerCase().includes(search.toLowerCase()))
                        .map((t: any, i: number) => (
                          <div key={i} className="leading-relaxed text-neutral-300">
                            <span className="font-bold text-neutral-400">{t.speaker}: </span>
                            <span>{t.text}</span>
                          </div>
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        </section>
      </div>
    </div>
  );
}
