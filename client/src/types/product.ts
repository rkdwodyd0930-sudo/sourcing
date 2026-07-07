export type MatchedAttr = {
  brand: string;
  capacity: number;
  unit: string;
  quantity: number;
}

export type CoupangTarget = {
  name: string;
  price: string;
  link: string;
  image: string;
}

export type ProductItem = {
  "11st_name": string;
  "11st_price": string;
  "11st_link": string;
  "11st_image": string;
  is_matched: boolean;
  is_11st_cheaper_winner_chance?: boolean;
  price_difference?: number;
  matched_attr?: MatchedAttr;
  final_coupang_target?: CoupangTarget;
}