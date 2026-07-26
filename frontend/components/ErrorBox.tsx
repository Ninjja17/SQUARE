type Props = { message?: string; onRetry?: () => void };
export function ErrorBox({ message = "Something went wrong — please try again.", onRetry }: Props) {
  return (
    <div className="card border-red-500/30 text-center py-10">
      <p className="text-red-400 text-sm mb-4">{message}</p>
      {onRetry && (
        <button onClick={onRetry} className="btn-secondary text-sm">
          Retry
        </button>
      )}
    </div>
  );
}
