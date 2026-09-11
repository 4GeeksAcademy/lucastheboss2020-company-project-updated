/**
 * /uis/backoffice/incidents
 * 
 * Thin route page importer following the pattern from AGENTS.md:
 * "Keep route files under app/uis/* as thin importers."
 */

import { IncidentAnalyzer } from '../../../../uis/backoffice/IncidentAnalyzer';

export default function IncidentsPage() {
  return <IncidentAnalyzer />;
}
