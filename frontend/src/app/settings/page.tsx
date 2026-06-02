"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { Key, Save, Settings, UserCircle } from "lucide-react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Separator } from "@/components/ui/separator";
import { authApi, loadStoredToken } from "@/lib/api";
import type { User as UserType } from "@/types";

type ProfileForm = { first_name: string; last_name: string; phone: string };
type PasswordForm = { current_password: string; new_password: string; confirm_password: string };

export default function SettingsPage() {
  const [user, setUser] = useState<UserType | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { isDirty },
  } = useForm<ProfileForm>();

  const {
    register: pwRegister,
    handleSubmit: pwHandleSubmit,
    reset: pwReset,
    formState: { errors: pwErrors },
    watch: pwWatch,
  } = useForm<PasswordForm>();

  useEffect(() => {
    loadStoredToken();
    authApi.me().then((u) => {
      setUser(u);
      reset({ first_name: u.first_name, last_name: u.last_name, phone: u.phone || "" });
    });
  }, [reset]);

  const onSaveProfile = async (data: ProfileForm) => {
    setSavingProfile(true);
    try {
      const updated = await authApi.updateMe({
        first_name: data.first_name,
        last_name: data.last_name,
        phone: data.phone || undefined,
      });
      setUser(updated);
      reset({ first_name: updated.first_name, last_name: updated.last_name, phone: updated.phone || "" });
      toast.success("Profile updated successfully");
    } catch {
      toast.error("Failed to update profile");
    } finally {
      setSavingProfile(false);
    }
  };

  const onChangePassword = async (data: PasswordForm) => {
    if (data.new_password !== data.confirm_password) {
      toast.error("Passwords don't match");
      return;
    }
    setSavingPassword(true);
    try {
      await authApi.changePassword(data.current_password, data.new_password);
      toast.success("Password changed successfully");
      pwReset();
    } catch (err: unknown) {
      const msg = (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      toast.error(msg || "Failed to change password");
    } finally {
      setSavingPassword(false);
    }
  };

  return (
    <AppLayout>
      <div className="p-6">
        <div className="mb-8 flex items-center gap-3">
          <Settings className="h-6 w-6 text-primary" />
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Settings</h1>
            <p className="text-sm text-muted-foreground">Manage your account and preferences</p>
          </div>
        </div>

        <div className="max-w-2xl space-y-6">
          {/* Profile */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <UserCircle className="h-4 w-4 text-primary" />
                  Profile
                </CardTitle>
                <CardDescription>Update your personal information</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit(onSaveProfile)} className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">First name</label>
                      <Input {...register("first_name", { required: true })} />
                    </div>
                    <div>
                      <label className="mb-1.5 block text-sm font-medium">Last name</label>
                      <Input {...register("last_name", { required: true })} />
                    </div>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">Email</label>
                    <Input value={user?.email || ""} disabled className="bg-muted opacity-60" />
                    <p className="mt-1 text-xs text-muted-foreground">Email cannot be changed</p>
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">Phone</label>
                    <Input {...register("phone")} placeholder="+1 555 000 0000" />
                  </div>
                  <Button
                    type="submit"
                    loading={savingProfile}
                    disabled={!isDirty}
                    size="sm"
                  >
                    <Save className="h-4 w-4" />
                    Save changes
                  </Button>
                </form>
              </CardContent>
            </Card>
          </motion.div>

          {/* Password */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Key className="h-4 w-4 text-primary" />
                  Change Password
                </CardTitle>
                <CardDescription>Update your account password</CardDescription>
              </CardHeader>
              <CardContent>
                <form onSubmit={pwHandleSubmit(onChangePassword)} className="space-y-4">
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">Current password</label>
                    <Input
                      type="password"
                      placeholder="••••••••"
                      {...pwRegister("current_password", { required: true })}
                    />
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">New password</label>
                    <Input
                      type="password"
                      placeholder="Min 8 characters"
                      {...pwRegister("new_password", { required: true, minLength: 8 })}
                    />
                    {pwErrors.new_password && (
                      <p className="mt-1 text-xs text-destructive">Minimum 8 characters</p>
                    )}
                  </div>
                  <div>
                    <label className="mb-1.5 block text-sm font-medium">Confirm new password</label>
                    <Input
                      type="password"
                      placeholder="••••••••"
                      {...pwRegister("confirm_password", {
                        required: true,
                        validate: (val) => val === pwWatch("new_password") || "Passwords don't match",
                      })}
                    />
                    {pwErrors.confirm_password && (
                      <p className="mt-1 text-xs text-destructive">{pwErrors.confirm_password.message}</p>
                    )}
                  </div>
                  <Button type="submit" loading={savingPassword} size="sm">
                    <Key className="h-4 w-4" />
                    Change password
                  </Button>
                </form>
              </CardContent>
            </Card>
          </motion.div>

          {/* Account Info */}
          <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Account Information</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Role</span>
                  <span className="font-medium capitalize">{user?.role?.replace("_", " ")}</span>
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Account status</span>
                  <span className="font-medium text-green-600 dark:text-green-400">Active</span>
                </div>
                <Separator />
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">Member since</span>
                  <span className="font-medium">
                    {user?.created_at
                      ? new Date(user.created_at).toLocaleDateString("en-US", {
                          month: "long",
                          year: "numeric",
                        })
                      : "—"}
                  </span>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </AppLayout>
  );
}
