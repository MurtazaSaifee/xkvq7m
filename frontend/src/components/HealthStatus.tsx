import { useHealthQuery } from "../api/queries";
import { StatusBadge } from "./StatusBadge";

export function HealthStatus() {
  const health = useHealthQuery();

  if (health.isError) {
    return <StatusBadge tone="danger" label="API unreachable" />;
  }
  if (health.isSuccess) {
    return <StatusBadge tone="ok" label="API healthy" />;
  }
  return <StatusBadge tone="neutral" label="Checking API" />;
}
