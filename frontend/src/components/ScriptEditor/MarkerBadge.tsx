import React from "react";
import { MARKER_COLORS } from "./types";

interface Props {
  marker: string;
}

export const MarkerBadge: React.FC<Props> = ({ marker }) => {
  const colorClass = MARKER_COLORS[marker.toLowerCase()] ?? "bg-gray-200 text-gray-800";
  return (
    <span
      className={`inline-block px-1 py-0.5 rounded text-xs font-mono mx-0.5 ${colorClass}`}
      aria-label={`emotional marker: ${marker}`}
    >
      [{marker}]
    </span>
  );
};
