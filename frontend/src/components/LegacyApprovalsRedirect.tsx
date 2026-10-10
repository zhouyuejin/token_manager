import { Navigate, useLocation } from 'react-router-dom'
import { legacyApprovalPath } from '../utils/approvalNavigation.mjs'

export default function LegacyApprovalsRedirect() {
  const { search, hash } = useLocation()
  return <Navigate to={legacyApprovalPath(search, hash)} replace />
}
