import { ConnectionStatus } from "../types";

interface Props {
  status:    ConnectionStatus;
  lastEvent: string | null;
}

export function LiveFeed({ status, lastEvent }: Props) {
  return (
    <div className="livefeed">
      <div className="livefeed-left">
        <span className={`livedot livedot-${status}`} />
        <span className="livefeed-label">
          {status === "connected"  ? "Live"         :
           status === "connecting" ? "Connecting…"  :
                                    "Reconnecting"}
        </span>
        {status === "connected" && (
          <span className="livefeed-sub">
            Events stream open · new PRs appear instantly
          </span>
        )}
      </div>
      {lastEvent && (
        <div className="livefeed-last">
          Last event: <strong>{lastEvent}</strong>
        </div>
      )}
    </div>
  );
}
