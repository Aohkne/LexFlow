import { useSyncExternalStore } from "react";

// Cầu nối SSR-an toàn: server luôn trả `false`, client trả `true` ngay sau khi
// hydrate xong — dùng để trì hoãn UI phụ thuộc trạng thái chỉ có ở trình duyệt
// (theme đã resolve, localStorage...) mà không set-state trong effect.
const subscribe = () => () => {};

export function useHasMounted() {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}
