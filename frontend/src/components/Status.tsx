import { label } from "../types";
export function Status({ value }: { value: string }) {
  return (
    <span className={"status " + value}>
      <span className="dot" />
      {label(value)}
    </span>
  );
}
