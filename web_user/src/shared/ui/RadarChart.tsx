import { Radar, RadarChart as RechartsRadar, PolarGrid, PolarAngleAxis, PolarRadiusAxis, ResponsiveContainer, Tooltip } from 'recharts';

export interface LifestyleData {
  cleanliness: number;
  extroversion: number;
  earlyBird: number;
  cooking: number;
  guestTolerance: number;
}

interface Props {
  myLifestyle?: LifestyleData;
  otherLifestyle?: LifestyleData;
}

const AXIS_LABELS = {
  cleanliness: "Ngăn nắp",
  extroversion: "Hướng ngoại",
  earlyBird: "Ngủ sớm",
  cooking: "Nấu ăn",
  guestTolerance: "Khách tới chơi",
};

export function RadarChart({ myLifestyle, otherLifestyle }: Props) {
  const data = Object.keys(AXIS_LABELS).map((key) => {
    const k = key as keyof LifestyleData;
    return {
      subject: AXIS_LABELS[k],
      A: myLifestyle ? myLifestyle[k] : 0,
      B: otherLifestyle ? otherLifestyle[k] : 0,
      fullMark: 5,
    };
  });

  return (
    <div className="w-full h-[300px]">
      <ResponsiveContainer width="100%" height="100%">
        <RechartsRadar cx="50%" cy="50%" outerRadius="80%" data={data}>
          <PolarGrid />
          <PolarAngleAxis dataKey="subject" className="text-xs" />
          <PolarRadiusAxis angle={30} domain={[0, 5]} tick={false} />
          <Tooltip />
          {myLifestyle && (
            <Radar name="Bạn" dataKey="A" stroke="#8884d8" fill="#8884d8" fillOpacity={0.6} />
          )}
          {otherLifestyle && (
            <Radar name="Họ" dataKey="B" stroke="#82ca9d" fill="#82ca9d" fillOpacity={0.6} />
          )}
        </RechartsRadar>
      </ResponsiveContainer>
    </div>
  );
}
