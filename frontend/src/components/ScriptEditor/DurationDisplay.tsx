import React from "react";
import { formatDuration } from "./types";

interface Props {
  estimatedDurationSec: number;
}

export const DurationDisplay: React.FC<Props> = ({ estimatedDurationSec }) => (
  <span className="text-sm text-gray-500">
    Estimated duration: <strong>{formatDuration(estimatedDurationSec)}</strong>
  </span>
);
