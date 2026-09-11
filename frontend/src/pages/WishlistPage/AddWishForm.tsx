import { useEffect, useState } from "react";
import { useWishlistStore } from "@/stores/wishlistStore";
import { useItineraryStore } from "@/stores/itineraryStore";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";

const inputCls =
  "w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-brand-400 focus:bg-white";

export function AddWishForm({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const add = useWishlistStore((s) => s.add);
  const destination = useItineraryStore((s) => s.itinerary?.destination ?? "");

  const [name, setName] = useState("");
  const [location, setLocation] = useState("");
  const [city, setCity] = useState("");
  const [notes, setNotes] = useState("");

  useEffect(() => {
    if (open) {
      setName("");
      setLocation("");
      setCity(destination);
      setNotes("");
    }
  }, [open, destination]);

  const submit = () => {
    if (!name.trim()) return;
    add({
      name: name.trim(),
      location: location.trim(),
      city: city.trim(),
      notes: notes.trim() || undefined,
      source: "manual",
    });
    onClose();
  };

  return (
    <Modal open={open} title="添加打卡心愿" onClose={onClose} width="max-w-md">
      <div className="space-y-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">名称 *</label>
          <input
            className={inputCls}
            value={name}
            placeholder="如：大熊猫繁育研究基地"
            onChange={(e) => setName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && submit()}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">地点</label>
            <input
              className={inputCls}
              value={location}
              placeholder="详细地址"
              onChange={(e) => setLocation(e.target.value)}
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-slate-500">城市</label>
            <input
              className={inputCls}
              value={city}
              placeholder="如：成都"
              onChange={(e) => setCity(e.target.value)}
            />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">备注</label>
          <textarea
            className={`${inputCls} resize-none`}
            rows={2}
            value={notes}
            placeholder="如：需要提前买门票"
            onChange={(e) => setNotes(e.target.value)}
          />
        </div>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onClose}>
          取消
        </Button>
        <Button size="sm" disabled={!name.trim()} onClick={submit}>
          添加
        </Button>
      </div>
    </Modal>
  );
}
