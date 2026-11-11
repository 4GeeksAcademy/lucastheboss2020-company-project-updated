"use client";

import { useState } from "react";
import type { FormEvent } from "react";
import { trackFlowAuthHeaders } from "../../src/utils/auth-headers";

interface KnowledgeAnswer {
  answer?: string;
  detail?: string;
}

export default function KnowledgeAssistant() {
  const [question, setQuestion] = useState("");
  const [answer, setAnswer] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function submitQuestion(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const cleanQuestion = question.trim();
    if (!cleanQuestion) {
      setError("Enter a question to search the TrackFlow knowledge base.");
      setAnswer("");
      return;
    }

    setLoading(true);
    setError("");
    setAnswer("");
    try {
      const response = await fetch("/api/backend/knowledge/query", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...trackFlowAuthHeaders(),
        },
        body: JSON.stringify({ question: cleanQuestion }),
        cache: "no-store",
      });
      const payload = (await response.json()) as KnowledgeAnswer;
      if (!response.ok) {
        if (response.status === 401) {
          throw new Error("Sign in to use the commercial knowledge assistant.");
        }
        throw new Error(payload.detail ?? "The knowledge request could not be completed.");
      }
      if (typeof payload.answer !== "string" || !payload.answer.trim()) {
        throw new Error("The knowledge service returned no answer.");
      }
      setAnswer(payload.answer);
    } catch (requestError: unknown) {
      setError(requestError instanceof Error ? requestError.message : "The knowledge request failed. Please retry.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <section>
      <header className="page-header">
        <span className="badge green">TrackFlow commercial team</span>
        <h1>Knowledge assistant</h1>
        <p>Answers are grounded in the approved delivery, returns, carrier, and storage documents.</p>
      </header>

      <section className="panel" aria-label="Ask the TrackFlow knowledge base">
        <form onSubmit={submitQuestion}>
          <label className="field" htmlFor="knowledge-question">
            <span>Your question</span>
            <textarea
              id="knowledge-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              maxLength={2000}
              required
              rows={4}
              placeholder="What is the standard return window?"
              aria-describedby="knowledge-question-count"
            />
          </label>
          <div className="actions" style={{ alignItems: "center", marginTop: "12px" }}>
            <span id="knowledge-question-count" className="message">
              {question.length}/2000
            </span>
            <button className="button" type="submit" disabled={loading || !question.trim()}>
              {loading ? "Searching documents…" : "Ask question"}
            </button>
          </div>
        </form>
      </section>

      {loading && <p className="message loading" role="status">Searching approved sources and preparing an answer…</p>}
      {error && <div className="message error" role="alert"><p>{error}</p></div>}
      {answer && (
        <section className="panel" aria-label="Grounded answer" aria-live="polite">
          <h2>Answer</h2>
          <p style={{ whiteSpace: "pre-wrap" }}>{answer}</p>
        </section>
      )}
    </section>
  );
}
