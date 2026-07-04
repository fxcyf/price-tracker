import { useEffect } from "react";
import { useSearchParams, useNavigate } from "react-router-dom";

function extractUrl(params: URLSearchParams): string | null {
  const url = params.get("url");
  if (url?.startsWith("http")) return url;

  const text = params.get("text");
  if (text) {
    const match = text.match(/https?:\/\/\S+/);
    if (match) return match[0];
  }

  return null;
}

export default function ShareTargetPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  useEffect(() => {
    const sharedUrl = extractUrl(searchParams);
    navigate("/", { replace: true, state: { sharedUrl } });
  }, [searchParams, navigate]);

  return null;
}
