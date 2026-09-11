import { useEffect, useState } from "react";
import { ACTIVITY_CATEGORIES, type ActivityCategory } from "@/types/itinerary";
import { Button } from "@/components/ui/Button";
import { Modal } from "@/components/ui/Modal";

export interface ActivityFormState {
  time: string;
  name: string;
  location: string;
  category: ActivityCategory;
  cost: string;
  notes: string;
}

const TIME_PATTERN = /^([01]\d|2[0-3]):[0-5]\d-([01]\d|2[0-3]):[0-5]\d$/;

const inputCls =
  "w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 outline-none transition-colors placeholder:text-slate-400 focus:border-brand-400 focus:bg-white";

export function ActivityEditForm({
  open,
  title,
  initial,
  onClose,
  onSubmit,
}: {
  open: boolean;
  title: string;
  initial: ActivityFormState;
  onClose: () => void;
  onSubmit: (form: ActivityFormState) => void;
}) {
  const [form, setForm] = useState<ActivityFormState>(initial);
  const [timeError, setTimeError] = useState("");

  useEffect(() => {
    if (open) {
      setForm(initial);
      setTimeError("");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const set = <K extends keyof ActivityFormState>(key: K, value: ActivityFormState[K]) =>
    setForm((f) => ({ ...f, [key]: value }));

  const valid = form.name.trim() && form.time && TIME_PATTERN.test(form.time);

  const submit = () => {
    if (!valid) {
      setTimeError("时间格式应为 HH:MM-HH:MM，如 09:00-11:30");
      return;
    }
    onSubmit({ ...form, name: form.name.trim(), location: form.location.trim() });
  };

  return (
    <Modal open={open} title={title} onClose={onClose}>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">时间段 *</label>
          <input
            className={inputCls}
            value={form.time}
            placeholder="09:00-11:30"
            onChange={(e) => {
              set("time", e.target.value);
              setTimeError("");
            }}
          />
          {timeError && <p className="mt-1 text-xs text-red-500">{timeError}</p>}
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">分类</label>
          <select
            className={inputCls}
            value={form.category}
            onChange={(e) => set("category", e.target.value as ActivityCategory)}
          >
            {ACTIVITY_CATEGORIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </div>
        <div className="col-span-2">
          <label className="mb-1 block text-xs font-medium text-slate-500">活动名称 *</label>
          <input
            className={inputCls}
            value={form.name}
            placeholder="如：参观宽窄巷子"
            onChange={(e) => set("name", e.target.value)}
          />
        </div>
        <div className="col-span-2">
          <label className="mb-1 block text-xs font-medium text-slate-500">地点</label>
          <input
            className={inputCls}
            value={form.location}
            placeholder="如：宽窄巷子"
            onChange={(e) => set("location", e.target.value)}
          />
        </div>
        <div>
          <label className="mb-1 block text-xs font-medium text-slate-500">费用（元）</label>
          <input
            className={inputCls}
            type="number"
            min="0"
            value={form.cost}
            onChange={(e) => set("cost", e.target.value)}
          />
        </div>
        <div className="col-span-2">
          <label className="mb-1 block text-xs font-medium text-slate-500">备注</label>
          <textarea
            className={`${inputCls} resize-none`}
            rows={2}
            value={form.notes}
            placeholder="如：需提前预约"
            onChange={(e) => set("notes", e.target.value)}
          />
        </div>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" size="sm" onClick={onClose}>
          取消
        </Button>
        <Button size="sm" onClick={submit}>
          保存
        </Button>
      </div>
    </Modal>
  );
}
