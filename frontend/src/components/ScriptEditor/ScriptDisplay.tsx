import React from "react";
import { MarkerBadge } from "./MarkerBadge";
import { VALID_MARKERS } from "./types";

interface Props {
  text: string;
}

const MARKER_SPLIT = /(\[[a-zA-Z]+\])/g;

export const ScriptDisplay: React.FC<Props> = ({ text }) => {
  const parts = text.split(MARKER_SPLIT);

  return (
    <p className="leading-relaxed text-gray-800 whitespace-pre-wrap">
      {parts.map((part, i) => {
        const match = part.match(/^\[([a-zA-Z]+)\]$/);
        if (match && VALID_MARKERS.has(match[1].toLowerCase())) {
          return <MarkerBadge key={i} marker={match[1].toLowerCase()} />;
        }
        return <React.Fragment key={i}>{part}</React.Fragment>;
      })}
    </p>
  );
};
