import { AppBar, Box, Button, Toolbar, Typography } from '@mui/material'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'

export function NavBar() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  if (!user) return null

  return (
    <AppBar position="static" color="default" elevation={1}>
      <Toolbar variant="dense">
        <Typography variant="subtitle1" sx={{ flexGrow: 0, mr: 3 }}>
          Text-to-SQL &amp; Doc Chat
        </Typography>
        <Button component={Link} to="/dashboard">
          Sources
        </Button>
        <Button component={Link} to="/chat">
          Chat
        </Button>
        <Box flexGrow={1} />
        <Typography variant="body2" sx={{ mr: 2 }}>
          {user.email}
        </Typography>
        <Button
          size="small"
          onClick={() => {
            logout()
            navigate('/login')
          }}
        >
          Sign out
        </Button>
      </Toolbar>
    </AppBar>
  )
}
