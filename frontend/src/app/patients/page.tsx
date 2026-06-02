"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Activity, ChevronRight, Plus, Search, User, Users } from "lucide-react";
import { toast } from "sonner";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { AppLayout } from "@/components/layout/AppLayout";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { patientsApi, triageApi } from "@/lib/api";
import { cn, formatRelative, initials } from "@/lib/utils";
import type { Patient } from "@/types";

const newPatientSchema = z.object({
  first_name: z.string().min(1),
  last_name: z.string().min(1),
  email: z.string().email().optional().or(z.literal("")),
  phone: z.string().optional(),
});
type NewPatientForm = z.infer<typeof newPatientSchema>;

export default function PatientsPage() {
  const [patients, setPatients] = useState<Patient[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [showNew, setShowNew] = useState(false);
  const [creating, setCreating] = useState(false);

  const { register, handleSubmit, reset, formState: { errors } } = useForm<NewPatientForm>({
    resolver: zodResolver(newPatientSchema),
  });

  const fetchPatients = useCallback(async () => {
    setLoading(true);
    try {
      const data = await patientsApi.list({
        page,
        size: 20,
        search: search || undefined,
      });
      setPatients(data.items);
      setTotalPages(data.pages);
      setTotal(data.total);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [page, search]);

  useEffect(() => {
    const t = setTimeout(fetchPatients, 300);
    return () => clearTimeout(t);
  }, [fetchPatients]);

  const onCreatePatient = async (data: NewPatientForm) => {
    setCreating(true);
    try {
      const patient = await patientsApi.create({
        first_name: data.first_name,
        last_name: data.last_name,
        email: data.email || undefined,
        phone: data.phone || undefined,
      });
      toast.success(`Patient ${patient.full_name} created`);
      setShowNew(false);
      reset();
      fetchPatients();
    } catch {
      toast.error("Failed to create patient");
    } finally {
      setCreating(false);
    }
  };

  const startTriage = async (patientId: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      const assessment = await triageApi.startSession(patientId);
      window.location.href = `/triage/${assessment.session_token}?assessment=${assessment.id}`;
    } catch {
      toast.error("Failed to start triage session");
    }
  };

  return (
    <AppLayout>
      <div className="p-6">
        {/* Header */}
        <div className="mb-6 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Patients</h1>
            <p className="mt-1 text-sm text-muted-foreground">
              {total} patient{total !== 1 ? "s" : ""} in your organization
            </p>
          </div>
          <Button variant="brand" size="sm" onClick={() => setShowNew(!showNew)}>
            <Plus className="h-4 w-4" />
            New Patient
          </Button>
        </div>

        {/* New Patient Form */}
        {showNew && (
          <motion.div
            initial={{ opacity: 0, y: -8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6"
          >
            <Card className="border-primary/30 bg-primary/5">
              <CardHeader className="pb-3">
                <CardTitle className="text-base">Add New Patient</CardTitle>
              </CardHeader>
              <CardContent>
                <form onSubmit={handleSubmit(onCreatePatient)} className="space-y-3">
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-xs font-medium">First name *</label>
                      <Input {...register("first_name")} placeholder="John" className="h-8 text-sm" />
                      {errors.first_name && <p className="mt-0.5 text-xs text-destructive">Required</p>}
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium">Last name *</label>
                      <Input {...register("last_name")} placeholder="Smith" className="h-8 text-sm" />
                      {errors.last_name && <p className="mt-0.5 text-xs text-destructive">Required</p>}
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="mb-1 block text-xs font-medium">Email</label>
                      <Input {...register("email")} type="email" placeholder="optional" className="h-8 text-sm" />
                    </div>
                    <div>
                      <label className="mb-1 block text-xs font-medium">Phone</label>
                      <Input {...register("phone")} placeholder="optional" className="h-8 text-sm" />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button type="submit" size="sm" loading={creating}>Create patient</Button>
                    <Button type="button" size="sm" variant="outline" onClick={() => { setShowNew(false); reset(); }}>
                      Cancel
                    </Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </motion.div>
        )}

        {/* Search */}
        <div className="mb-4 relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            className="pl-9"
            placeholder="Search patients by name or email…"
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          />
        </div>

        {loading ? (
          <div className="space-y-2">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i} className="skeleton h-16 rounded-xl" />
            ))}
          </div>
        ) : patients.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border py-16">
            <Users className="mb-3 h-10 w-10 text-muted-foreground/40" />
            <p className="font-medium text-muted-foreground">
              {search ? "No patients match your search" : "No patients yet"}
            </p>
            {!search && (
              <Button className="mt-4" size="sm" variant="brand" onClick={() => setShowNew(true)}>
                <Plus className="h-4 w-4" />
                Add first patient
              </Button>
            )}
          </div>
        ) : (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2">
            {patients.map((patient, i) => (
              <motion.div
                key={patient.id}
                initial={{ opacity: 0, y: 6 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.04 }}
              >
                <Link href={`/patients/${patient.id}`}>
                  <Card className="cursor-pointer transition-all hover:border-primary/30 hover:shadow-md">
                    <CardContent className="p-4">
                      <div className="flex items-center gap-4">
                        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary">
                          {initials(patient.full_name)}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="font-medium">{patient.full_name}</p>
                          <div className="mt-0.5 flex items-center gap-2 text-xs text-muted-foreground">
                            {patient.age && <span>{patient.age} yrs</span>}
                            {patient.biological_sex && (
                              <span className="capitalize">{patient.biological_sex}</span>
                            )}
                            {patient.email && <span>· {patient.email}</span>}
                            {patient.phone && <span>· {patient.phone}</span>}
                          </div>
                          <div className="mt-1 flex flex-wrap gap-1">
                            {(patient.chronic_conditions as string[]).slice(0, 3).map((c) => (
                              <Badge key={c} variant="secondary" className="text-[10px]">
                                {c}
                              </Badge>
                            ))}
                            {patient.allergies.length > 0 && (
                              <Badge variant="outline" className="text-[10px] text-orange-600 border-orange-500/30">
                                {patient.allergies.length} allerg{patient.allergies.length > 1 ? "ies" : "y"}
                              </Badge>
                            )}
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          <span className="text-xs text-muted-foreground">
                            {formatRelative(patient.created_at)}
                          </span>
                          <button
                            onClick={(e) => startTriage(patient.id, e)}
                            className="flex items-center gap-1 rounded-lg bg-primary/10 px-2.5 py-1.5 text-xs font-medium text-primary transition-colors hover:bg-primary hover:text-primary-foreground"
                          >
                            <Activity className="h-3 w-3" />
                            Triage
                          </button>
                          <ChevronRight className="h-4 w-4 text-muted-foreground" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              </motion.div>
            ))}
          </motion.div>
        )}

        {/* Pagination */}
        {!loading && totalPages > 1 && (
          <div className="mt-6 flex items-center justify-center gap-2">
            <Button variant="outline" size="sm" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              Previous
            </Button>
            <span className="text-sm text-muted-foreground">Page {page} of {totalPages}</span>
            <Button variant="outline" size="sm" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>
              Next
            </Button>
          </div>
        )}
      </div>
    </AppLayout>
  );
}
