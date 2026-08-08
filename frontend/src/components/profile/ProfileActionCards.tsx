import { Button, Card } from 'antd'
import { SettingOutlined, SlidersOutlined } from '@ant-design/icons'
import type { ProfileOutletKey } from '../../types/profile'

type ProfileActionCardsProps = {
  activeOutlet: ProfileOutletKey
  onOutletChange: (outlet: ProfileOutletKey) => void
}

export function ProfileActionCards({ activeOutlet, onOutletChange }: ProfileActionCardsProps) {
  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card
        className={[
          'rounded-2xl border shadow-sm transition',
          activeOutlet === 'preferences' ? 'border-blue-200 bg-blue-50/60' : 'border-transparent bg-white',
        ].join(' ')}
        styles={{ body: { padding: 20 } }}
      >
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[18px] font-bold text-slate-900">
              <SlidersOutlined className="text-blue-600" />
              我的偏好
            </div>
            <div className="mt-2 text-[13px] text-slate-500">维护旅行主题、预算和交通方式偏好。</div>
          </div>
          <Button type={activeOutlet === 'preferences' ? 'primary' : 'default'} onClick={() => onOutletChange('preferences')}>
            打开
          </Button>
        </div>
      </Card>

      <Card
        className={[
          'rounded-2xl border shadow-sm transition',
          activeOutlet === 'settings' ? 'border-blue-200 bg-blue-50/60' : 'border-transparent bg-white',
        ].join(' ')}
        styles={{ body: { padding: 20 } }}
      >
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-[18px] font-bold text-slate-900">
              <SettingOutlined className="text-blue-600" />
              设置
            </div>
            <div className="mt-2 text-[13px] text-slate-500">管理主题语言、账号操作和本地数据。</div>
          </div>
          <Button type={activeOutlet === 'settings' ? 'primary' : 'default'} onClick={() => onOutletChange('settings')}>
            打开
          </Button>
        </div>
      </Card>
    </div>
  )
}
