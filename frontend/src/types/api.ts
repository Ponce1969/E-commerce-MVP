export type UserRole = "ADMIN" | "CUSTOMER";

export interface TokenResponse {
  access_token: string;
  token_type: string;
  role: UserRole;
  email: string;
  commercial_list_id: number | null;
  user_id: number;
}

export interface ProductPriceDetail {
  commercial_list_id: number;
  commercial_list_name: string;
  cost_iva_inc: number | null;
  markup_percentage: number | null;
  price_iva_inc: number | null;
  has_conflict: boolean;
  conflict_detail: string | null;
}

export interface ProductAdminDetail {
  id: number;
  code: string | null;
  name: string;
  presentation: string | null;
  provider: string | null;
  category: string;
  iva_rate: number;
  is_published: boolean;
  is_pending_draft: boolean;
  tech_sheet_url: string | null;
  image_url: string | null;
  is_active: boolean;
  current_stock: number;
  min_stock_alert: number;
  allow_backorder: boolean;
  is_low_stock: boolean;
  is_out_of_stock: boolean;
  prices: ProductPriceDetail[];
}

export interface ProductStockUpdate {
  current_stock: number;
  min_stock_alert: number;
  allow_backorder: boolean;
}

export interface ProductPortalItem {
  id: number;
  name: string;
  presentation: string | null;
  category: string;
  price_iva_inc: number;
  iva_rate: number;
  image_url: string | null;
  tech_sheet_url: string | null;
}

export type DeliveryType = "PICKUP_PASO_MOLINO" | "CADETERIA_MARCO_POSTAL";
export type OrderStatus =
  | "PENDIENTE"
  | "CONFIRMADO"
  | "EN_PREPARACION"
  | "DESPACHADO"
  | "ENTREGADO"
  | "CANCELADO";

export interface OrderItemCreate {
  product_id: number;
  quantity: number;
}

export interface OrderCreate {
  delivery_type: DeliveryType;
  delivery_address?: string | null;
  delivery_notes?: string | null;
  items: OrderItemCreate[];
}

export interface OrderItemResponse {
  id: number;
  product_id: number;
  product_name: string;
  quantity: number;
  unit_price: number;
  discount_percent: number;
  subtotal: number;
}

export interface OrderResponse {
  id: number;
  customer_id: number;
  order_status: OrderStatus;
  delivery_type: DeliveryType;
  delivery_cost: number;
  total_amount: number;
  delivery_address: string | null;
  delivery_notes: string | null;
  created_at: string;
  items: OrderItemResponse[];
}
