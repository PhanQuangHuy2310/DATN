import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Search, MapPin } from "lucide-react";
import { Button, Select } from "@/shared/ui";
import { QUICK_DISTRICTS, PRICE_RANGE, formatCurrency } from "@/shared/lib";
import { filtersToParams } from "./filterParams";

const PRICE_OPTIONS = [
  { value: "", label: "Mọi mức giá" },
  { value: "0-3000000", label: `Dưới ${formatCurrency(3_000_000)}` },
  { value: "3000000-5000000", label: "3 - 5 triệu" },
  { value: "5000000-8000000", label: "5 - 8 triệu" },
  { value: `8000000-${PRICE_RANGE.max}`, label: "Trên 8 triệu" },
];

export function QuickSearchForm() {
  const navigate = useNavigate();
  const [district, setDistrict] = useState("");
  const [price, setPrice] = useState("");

  const submit = () => {
    const [priceMin, priceMax] = price ? price.split("-").map(Number) : [];
    const params = filtersToParams({
      type: "RENTAL",
      district: district || undefined,
      priceMin,
      priceMax,
    });
    navigate(`/search?${params.toString()}`);
  };

  return (
    <div className="flex flex-col gap-3 rounded-[15px] border border-line bg-white p-4 sm:flex-row sm:items-end">
      <div className="flex-1">
        <label htmlFor="district" className="mb-1.5 block text-[13px] font-medium text-graphite">Khu vực</label>
        <Select
          name="district"
          value={district}
          onChange={(e) => setDistrict(e.target.value)}
          placeholder="Mọi khu vực"
          options={QUICK_DISTRICTS.map((d) => ({ value: d, label: d }))}
        />
      </div>
      <div className="flex-1">
        <label htmlFor="price" className="mb-1.5 block text-[13px] font-medium text-graphite">Mức giá</label>
        <Select
          name="price"
          value={price}
          onChange={(e) => setPrice(e.target.value)}
          options={PRICE_OPTIONS}
        />
      </div>
      <Button size="lg" className="sm:w-auto" onClick={submit}>
        <Search className="size-4" /> Tìm kiếm
      </Button>
    </div>
  );
}

export function DistrictQuickLinks() {
  const navigate = useNavigate();
  return (
    <div className="flex flex-wrap gap-2">
      {QUICK_DISTRICTS.map((d) => (
        <button
          key={d}
          type="button"
          onClick={() =>
            navigate(`/search?${filtersToParams({ type: "RENTAL", district: d })}`)
          }
          className="inline-flex items-center gap-1.5 rounded-full border border-line bg-white px-3.5 py-1.5 text-sm text-graphite transition-colors hover:border-cobalt hover:text-cobalt"
        >
          <MapPin className="size-3.5" /> {d}
        </button>
      ))}
    </div>
  );
}
