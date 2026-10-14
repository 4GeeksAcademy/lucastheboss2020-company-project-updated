"use client";

import type { RecordValidationError } from "../../src/incidents/types";

interface IncidentInvalidRecordDetailsProps {
  records: RecordValidationError[];
}

export default function IncidentInvalidRecordDetails({ records }: IncidentInvalidRecordDetailsProps) {
  return (
    <div className="detail-grid">
      {records.map((record) => (
        <article className="candidate-card" key={record.row_number}>
          <p><strong>Row {record.row_number}</strong> · ID: {record.incident_id || "N/A"}</p>
          <ul>
            {record.errors.map((error) => <li key={error}>{error}</li>)}
          </ul>
        </article>
      ))}
    </div>
  );
}
