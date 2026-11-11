"use client";

import { useEffect, useRef, useState } from "react";
import { userSafeErrorMessage } from "../utils/api-errors";

interface AsyncResource<T> {
  data: T | null;
  loading: boolean;
  error: string;
  retry: () => void;
}

export function useAsyncResource<T>(
  resourceKey: string,
  load: () => Promise<T>,
  fallbackMessage: string,
): AsyncResource<T> {
  const loadRef = useRef(load);
  loadRef.current = load;

  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [retryVersion, setRetryVersion] = useState(0);

  useEffect(() => {
    let ignore = false;
    setLoading(true);
    setError("");

    loadRef.current()
      .then((result) => { if (!ignore) setData(result); })
      .catch((requestError: unknown) => {
        if (!ignore) setError(userSafeErrorMessage(requestError, fallbackMessage));
      })
      .finally(() => { if (!ignore) setLoading(false); });

    return () => { ignore = true; };
  }, [resourceKey, retryVersion, fallbackMessage]);

  return {
    data,
    loading,
    error,
    retry: () => setRetryVersion((version) => version + 1),
  };
}