"use client";
import { useEffect, useState } from "react";
import { getIndex, getReport, type Index, type Report } from "./data";

export function useIndex() {
  const [index, setIndex] = useState<Index | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    getIndex().then(setIndex).catch((e) => setError(String(e.message ?? e)));
  }, []);
  return { index, error };
}

export function useReport(team: string, map: string) {
  const [report, setReport] = useState<Report | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!team || !map) return;
    setReport(null);
    getReport(team, map).then(setReport).catch((e) => setError(String(e.message ?? e)));
  }, [team, map]);
  return { report, error };
}
