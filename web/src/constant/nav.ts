export type NavItem = {
  href: string;
  label: string;
  icon: string;
};

// Điều hướng chính — dùng chung cho masthead nav (desktop) và bottom nav (mobile).
export const MAIN_NAV: NavItem[] = [
  { href: "/", label: "Trang chủ", icon: "ph:newspaper" },
  { href: "/chat", label: "Tra cứu", icon: "ph:chats-circle" },
  { href: "/graph", label: "Đồ thị", icon: "ph:graph" },
  { href: "/admin", label: "Quản trị", icon: "ph:shield-check" },
];
