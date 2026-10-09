export type InventoryWarehouse = "LA" | "ZGZ";
export type InventoryCategory = "fashion" | "electronics" | "cosmetics";
export type InventoryExitType = "dispatch" | "loss";

export interface InventoryProductSummary {
  id: number;
  name: string;
  sku: string;
  client_name: string;
  category: InventoryCategory;
  warehouse: InventoryWarehouse;
}

export interface InventoryProduct extends InventoryProductSummary {
  current_stock: number;
}

export interface InboundOrderInput {
  sku_id: number;
  quantity: number;
  reference: string;
  warehouse: InventoryWarehouse;
}

export interface OutboundOrderInput {
  sku_id: number;
  quantity: number;
  exit_type: InventoryExitType;
  tracking_number: string | null;
  warehouse: InventoryWarehouse;
}

export interface InventoryOrder {
  movement_type: "inbound" | "outbound";
  id: number;
  sku_id: number;
  quantity: number;
  warehouse: InventoryWarehouse;
  created_at: string;
  user_uuid: string;
  sku: InventoryProductSummary;
  reference?: string | null;
  exit_type?: InventoryExitType | null;
  tracking_number?: string | null;
}