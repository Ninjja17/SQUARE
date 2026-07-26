type Props = { children: React.ReactNode };
export function Spinner({ children }: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-20 gap-4 text-[#666]">
      <div className="w-8 h-8 border-2 border-[#333] border-t-white rounded-full animate-spin" />
      <p className="text-sm">{children}</p>
    </div>
  );
}
