import { useState, useEffect } from "react";
import { RadarChart, LifestyleData } from "@/shared/ui/RadarChart";
import { Button, useToast } from "@/shared/ui";
import { apiClient } from "@/shared/api";

export function LifestylePanel() {
  const toast = useToast();
  const [loading, setLoading] = useState(false);
  const [lifestyle, setLifestyle] = useState<LifestyleData>({
    cleanliness: 3,
    extroversion: 3,
    earlyBird: 3,
    cooking: 3,
    guestTolerance: 3,
  });

  useEffect(() => {
    apiClient.get<LifestyleData>("/api/roommates/lifestyle")
      .then((res) => {
        if (res.data) setLifestyle(res.data);
      })
      .catch(console.error);
  }, []);

  const handleChange = (key: keyof LifestyleData, val: number) => {
    setLifestyle((prev) => ({ ...prev, [key]: val }));
  };

  const handleSave = async () => {
    setLoading(true);
    try {
      await apiClient.put("/api/roommates/lifestyle", lifestyle);
      toast.success("Cập nhật hồ sơ thói quen thành công!");
    } catch (e) {
      toast.error("Có lỗi xảy ra");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <h3 className="text-lg font-medium">Hồ sơ Thói quen Sinh hoạt</h3>
      <p className="text-sm text-gray-500">Giúp hệ thống tìm kiếm người ở ghép phù hợp nhất với bạn.</p>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
        <div className="space-y-4">
          <SliderRow label="Sự ngăn nắp" value={lifestyle.cleanliness} onChange={(v) => handleChange("cleanliness", v)} left="Luộm thuộm" right="Sạch sẽ" />
          <SliderRow label="Tính cách" value={lifestyle.extroversion} onChange={(v) => handleChange("extroversion", v)} left="Hướng nội" right="Hướng ngoại" />
          <SliderRow label="Giờ ngủ" value={lifestyle.earlyBird} onChange={(v) => handleChange("earlyBird", v)} left="Cú đêm" right="Ngủ sớm" />
          <SliderRow label="Nấu ăn" value={lifestyle.cooking} onChange={(v) => handleChange("cooking", v)} left="Ăn ngoài" right="Thường xuyên nấu" />
          <SliderRow label="Khách tới chơi" value={lifestyle.guestTolerance} onChange={(v) => handleChange("guestTolerance", v)} left="Khép kín" right="Thoải mái" />
          
          <Button onClick={handleSave} loading={loading} className="w-full mt-4">Lưu hồ sơ</Button>
        </div>

        <div className="border rounded-lg p-4 bg-gray-50 flex items-center justify-center">
          <RadarChart myLifestyle={lifestyle} />
        </div>
      </div>
    </div>
  );
}

function SliderRow({ label, value, onChange, left, right }: { label: string, value: number, onChange: (v: number) => void, left: string, right: string }) {
  return (
    <div>
      <div className="flex justify-between mb-1">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className="text-sm text-gray-500">{value}/5</span>
      </div>
      <input 
        type="range" min="1" max="5" value={value} 
        onChange={(e) => onChange(Number(e.target.value))}
        className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer"
      />
      <div className="flex justify-between text-xs text-gray-400 mt-1">
        <span>{left}</span>
        <span>{right}</span>
      </div>
    </div>
  );
}
