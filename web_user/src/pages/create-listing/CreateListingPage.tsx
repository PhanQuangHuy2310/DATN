import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button, Input, Textarea, Select, Checkbox, useToast, Spinner } from "@/shared/ui";
import { cn } from "@/shared/lib/cn";
import { getErrorMessage } from "@/shared/api";
import {
  AMENITIES,
  ALLEY_TYPES,
  ALLEY_WIDTHS,
  ALLEY_DEPTHS,
} from "@/shared/lib";
import type {
  AlleyType,
  AlleyWidth,
  AlleyDepth,
  ListingType,
  RoommateGender,
} from "@/entities/listing";
import { useAuthStore } from "@/features/auth";
import { isLandlord } from "@/entities/user";
import type { LatLng } from "@/shared/types";
import { useListing } from "@/pages/listing-detail/hooks";
import { LocationPicker } from "./LocationPicker";
import { MediaUpload } from "./MediaUpload";
import { useCreateListing, useUpdateListing, type ListingPayload } from "./hooks";

interface FormState {
  type: ListingType;
  title: string;
  description: string;
  price: string;
  area: string;
  province: string;
  district: string;
  ward: string;
  address: string;
  coords: LatLng | null;
  alleyType: AlleyType | "";
  alleyWidth: AlleyWidth | "";
  alleyDepth: AlleyDepth | "";
  maxMotorbikes: string;
  gender: RoommateGender | "";
  amenityIds: string[];
  costs: { electric: string; water: string; wifi: string; cleaning: string; parking: string };
  mediaUrls: string[];
  videoUrl: string | null;
}

const EMPTY: FormState = {
  type: "RENTAL",
  title: "",
  description: "",
  price: "",
  area: "",
  province: "",
  district: "",
  ward: "",
  address: "",
  coords: null,
  alleyType: "",
  alleyWidth: "",
  alleyDepth: "",
  maxMotorbikes: "",
  gender: "",
  amenityIds: [],
  costs: { electric: "", water: "", wifi: "", cleaning: "", parking: "" },
  mediaUrls: [],
  videoUrl: null,
};

export function CreateListingPage() {
  const { id } = useParams<{ id: string }>();
  const isEdit = !!id;
  const navigate = useNavigate();
  const toast = useToast();
  const { user } = useAuthStore();
  const landlord = isLandlord(user);

  const [form, setForm] = useState<FormState>({ ...EMPTY, type: landlord ? "RENTAL" : "ROOMMATE" });

  const existing = useListing(id!);
  const create = useCreateListing();
  const update = useUpdateListing(id ?? "");

  // Prefill when editing.
  useEffect(() => {
    const l = existing.data;
    if (!isEdit || !l) return;
    setForm({
      type: l.type,
      title: l.title,
      description: l.description ?? "",
      price: String(l.price ?? ""),
      area: String(l.area ?? ""),
      province: l.province ?? "",
      district: l.district ?? "",
      ward: l.ward ?? "",
      address: l.address ?? "",
      coords: l.lat != null && l.lng != null ? { lat: l.lat, lng: l.lng } : null,
      alleyType: l.alleyType ?? "",
      alleyWidth: l.alleyWidth ?? "",
      alleyDepth: l.alleyDepth ?? "",
      maxMotorbikes: l.maxMotorbikes != null ? String(l.maxMotorbikes) : "",
      gender: l.gender ?? "",
      amenityIds: l.amenityIds ?? [],
      costs: {
        electric: l.costs?.electric?.toString() ?? "",
        water: l.costs?.water?.toString() ?? "",
        wifi: l.costs?.wifi?.toString() ?? "",
        cleaning: l.costs?.cleaning?.toString() ?? "",
        parking: l.costs?.parking?.toString() ?? "",
      },
      mediaUrls: l.mediaUrls ?? [],
      videoUrl: l.videoUrl ?? null,
    });
  }, [existing.data, isEdit]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setForm((f) => ({ ...f, [k]: v }));
  const setCost = (k: keyof FormState["costs"], v: string) =>
    setForm((f) => ({ ...f, costs: { ...f.costs, [k]: v } }));
  const toggleAmenity = (a: string) =>
    setForm((f) => ({
      ...f,
      amenityIds: f.amenityIds.includes(a)
        ? f.amenityIds.filter((x) => x !== a)
        : [...f.amenityIds, a],
    }));

  const pending = create.isPending || update.isPending;

  const buildPayload = (): ListingPayload | null => {
    if (!form.title.trim()) return toast.error("Vui lòng nhập tiêu đề tin đăng."), null;
    if (!form.price || Number(form.price) <= 0) return toast.error("Vui lòng nhập giá thuê hợp lệ."), null;
    if (!form.area || Number(form.area) <= 0) return toast.error("Vui lòng nhập diện tích hợp lệ."), null;
    if (!form.coords) return toast.error("Vui lòng ghim vị trí phòng trên bản đồ."), null;
    if (form.mediaUrls.length < 3)
      return toast.error("Vui lòng tải lên tối thiểu 3 ảnh thực tế."), null;

    const num = (s: string) => (s ? Number(s) : undefined);
    return {
      type: form.type,
      title: form.title.trim(),
      description: form.description.trim() || undefined,
      price: Number(form.price),
      area: Number(form.area),
      province: form.province || undefined,
      district: form.district || undefined,
      ward: form.ward || undefined,
      address: form.address || undefined,
      lat: form.coords.lat,
      lng: form.coords.lng,
      alleyType: form.alleyType || undefined,
      alleyWidth: form.alleyWidth || undefined,
      alleyDepth: form.alleyDepth || undefined,
      maxMotorbikes: num(form.maxMotorbikes),
      gender: form.type === "ROOMMATE" ? form.gender || undefined : undefined,
      amenityIds: form.amenityIds,
      costs: {
        electric: num(form.costs.electric),
        water: num(form.costs.water),
        wifi: num(form.costs.wifi),
        cleaning: num(form.costs.cleaning),
        parking: num(form.costs.parking),
      },
      mediaUrls: form.mediaUrls,
      videoUrl: form.videoUrl,
    };
  };

  const submit = () => {
    const payload = buildPayload();
    if (!payload) return;
    const mutation = isEdit ? update : create;
    mutation.mutate(payload, {
      onSuccess: (l) => {
        toast.success(isEdit ? "Đã cập nhật tin đăng." : "Đăng tin thành công — tin đang chờ duyệt.");
        navigate(`/listings/${l.id}`);
      },
      onError: (e) => toast.error(getErrorMessage(e)),
    });
  };

  const typeOptions = useMemo(
    () =>
      landlord
        ? ([
            { value: "RENTAL", label: "Phòng cho thuê độc lập" },
            { value: "ROOMMATE", label: "Tìm bạn ở ghép" },
          ] as const)
        : ([{ value: "ROOMMATE", label: "Tìm bạn ở ghép" }] as const),
    [landlord],
  );

  if (isEdit && existing.isLoading) {
    return (
      <div className="flex justify-center py-24">
        <Spinner className="size-8" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 sm:px-6">
      <h1 className="mb-6">{isEdit ? "Chỉnh sửa tin đăng" : "Đăng tin phòng trọ mới"}</h1>

      <div className="space-y-6">
        <Step n={1} title="Phân loại tin đăng">
          <div className="grid gap-2 sm:grid-cols-2">
            {typeOptions.map((o) => (
              <button
                key={o.value}
                type="button"
                onClick={() => set("type", o.value)}
                className={cn(
                  "rounded-[8.8px] border px-4 py-3 text-left text-sm font-medium transition-colors",
                  form.type === o.value
                    ? "border-cobalt bg-cobalt-soft text-cobalt"
                    : "border-line text-graphite hover:border-cobalt",
                )}
              >
                {o.label}
              </button>
            ))}
          </div>
          {form.type === "ROOMMATE" && (
            <div className="mt-3 max-w-xs">
              <Select
                label="Giới tính mong muốn"
                name="gender"
                placeholder="Không yêu cầu"
                value={form.gender}
                onChange={(e) => set("gender", e.target.value as RoommateGender)}
                options={[
                  { value: "MALE", label: "Nam" },
                  { value: "FEMALE", label: "Nữ" },
                  { value: "ANY", label: "Nam/Nữ" },
                ]}
              />
            </div>
          )}
        </Step>

        <Step n={2} title="Vị trí & bản đồ">
          <div className="grid gap-3 sm:grid-cols-2">
            <Input label="Tỉnh/Thành" name="province" value={form.province} onChange={(e) => set("province", e.target.value)} placeholder="Hà Nội" />
            <Input label="Quận/Huyện" name="district" value={form.district} onChange={(e) => set("district", e.target.value)} placeholder="Cầu Giấy" />
            <Input label="Phường/Xã" name="ward" value={form.ward} onChange={(e) => set("ward", e.target.value)} placeholder="Dịch Vọng" />
            <Input label="Số nhà / Tên đường" name="address" value={form.address} onChange={(e) => set("address", e.target.value)} placeholder="123 Cầu Giấy" />
          </div>
          <p className="mb-2 mt-4 text-[13px] font-medium text-graphite">Ghim tọa độ chính xác (bấm hoặc kéo marker)</p>
          <LocationPicker value={form.coords} onChange={(p) => set("coords", p)} />
          {form.coords && (
            <p className="mt-1.5 text-xs text-fog">
              Đã ghim: {form.coords.lat.toFixed(5)}, {form.coords.lng.toFixed(5)}
            </p>
          )}
        </Step>

        <Step n={3} title="Chi tiết phòng & giá cả">
          <Input label="Tiêu đề tin đăng" name="title" value={form.title} onChange={(e) => set("title", e.target.value)} placeholder="Phòng trọ khép kín 25m² gần ĐH Bách Khoa" />
          <div className="mt-3">
            <Textarea label="Mô tả phòng" name="description" value={form.description} onChange={(e) => set("description", e.target.value)} placeholder="Mô tả chi tiết: hướng phòng, nội thất, giờ giấc…" />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Input label="Giá thuê (VND/tháng)" name="price" type="number" min={0} value={form.price} onChange={(e) => set("price", e.target.value)} placeholder="3500000" />
            <Input label="Diện tích (m²)" name="area" type="number" min={0} value={form.area} onChange={(e) => set("area", e.target.value)} placeholder="25" />
          </div>
          <p className="mb-2 mt-4 text-[13px] font-medium text-graphite">Chi phí cố định (VND)</p>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Input label="Điện /kWh" name="cost-electric" type="number" value={form.costs.electric} onChange={(e) => setCost("electric", e.target.value)} placeholder="3800" />
            <Input label="Nước /người" name="cost-water" type="number" value={form.costs.water} onChange={(e) => setCost("water", e.target.value)} placeholder="100000" />
            <Input label="Wifi /phòng" name="cost-wifi" type="number" value={form.costs.wifi} onChange={(e) => setCost("wifi", e.target.value)} placeholder="100000" />
            <Input label="Vệ sinh /tháng" name="cost-cleaning" type="number" value={form.costs.cleaning} onChange={(e) => setCost("cleaning", e.target.value)} placeholder="50000" />
            <Input label="Gửi xe /xe" name="cost-parking" type="number" value={form.costs.parking} onChange={(e) => setCost("parking", e.target.value)} placeholder="80000" />
          </div>
        </Step>

        <Step n={4} title="Hạ tầng ngõ ngách & tiện ích">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Select label="Loại ngõ" name="alleyType" placeholder="—" value={form.alleyType} onChange={(e) => set("alleyType", e.target.value as AlleyType)} options={ALLEY_TYPES.map((o) => ({ value: o.value, label: o.label }))} />
            <Select label="Độ rộng ngõ" name="alleyWidth" placeholder="—" value={form.alleyWidth} onChange={(e) => set("alleyWidth", e.target.value as AlleyWidth)} options={ALLEY_WIDTHS.map((o) => ({ value: o.value, label: o.label }))} />
            <Select label="Độ sâu ngõ" name="alleyDepth" placeholder="—" value={form.alleyDepth} onChange={(e) => set("alleyDepth", e.target.value as AlleyDepth)} options={ALLEY_DEPTHS.map((o) => ({ value: o.value, label: o.label }))} />
            <Input label="Xe máy tối đa" name="maxMotorbikes" type="number" min={0} value={form.maxMotorbikes} onChange={(e) => set("maxMotorbikes", e.target.value)} placeholder="2" />
          </div>
          <p className="mb-2 mt-4 text-[13px] font-medium text-graphite">Tiện ích phòng</p>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
            {AMENITIES.map((a) => (
              <Checkbox key={a.id} name={`am-${a.id}`} label={a.label} checked={form.amenityIds.includes(a.id)} onChange={() => toggleAmenity(a.id)} />
            ))}
          </div>
        </Step>

        <Step n={5} title="Hình ảnh & video lộ trình">
          <MediaUpload
            images={form.mediaUrls}
            videoUrl={form.videoUrl}
            onImagesChange={(urls) => set("mediaUrls", urls)}
            onVideoChange={(url) => set("videoUrl", url)}
          />
        </Step>

        <div className="flex items-center justify-end gap-3 border-t border-line pt-5">
          <Button variant="ghost" onClick={() => navigate(-1)}>Hủy bỏ</Button>
          <Button onClick={submit} loading={pending}>
            {isEdit ? "Lưu thay đổi" : "Đăng tin ngay — chờ duyệt"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function Step({ n, title, children }: { n: number; title: string; children: ReactNode }) {
  return (
    <section className="rounded-[15px] border border-line bg-white p-5">
      <div className="mb-4 flex items-center gap-3">
        <span className="flex size-7 items-center justify-center rounded-full bg-cobalt text-sm font-semibold text-white">
          {n}
        </span>
        <h2 className="text-lg">{title}</h2>
      </div>
      {children}
    </section>
  );
}
