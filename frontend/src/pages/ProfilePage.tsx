import { ProfileLayout } from '../layouts/ProfileLayout'
import { useProfilePageData } from '../hooks/useProfilePageData'

export default function ProfilePage() {
  const profilePageData = useProfilePageData()

  return <ProfileLayout {...profilePageData} />
}
