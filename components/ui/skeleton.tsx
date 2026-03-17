import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "shimmer rounded-md bg-surface-raised",
        className
      )}
    />
  );
}

export function CardSkeleton() {
  return (
    <div className="card-base p-5 space-y-3">
      <Skeleton className="h-4 w-32" />
      <Skeleton className="h-10 w-24" />
      <Skeleton className="h-3 w-48" />
      <Skeleton className="h-16 w-full" />
    </div>
  );
}
